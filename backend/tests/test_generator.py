from datetime import date
from decimal import Decimal as D
from io import BytesIO

import pytest
from docx import Document

from app.engine.calculator import calculate_day_by_day_ledger
from app.engine.legal_templates import build_lawsuit, fmt_clp, fmt_date, fmt_uf
from app.schemas.instrument import Attorney, CourtJurisdiction, Pagare
from app.schemas.liquidation import Currency, DayCount, LiquidationParams
from app.services.generator import generate_lawsuit_docx

PARTY_C = {"name": "Banco Ejemplo SpA", "rut": "76.086.428-5"}
PARTY_D = {"name": "Juan Pérez", "rut": "12.345.678-5"}
ATT = Attorney(name="María Soto", rut="11.111.111-1", address="Huérfanos 1117, Santiago")


def pagare(**kw):
    base = dict(amount=D(1_000_000), currency=Currency.CLP, issue_date=date(2024, 1, 1),
                maturity_date=date(2024, 1, 31), agreed_rate_annual=D(24),
                creditor=PARTY_C, debtor=PARTY_D,
                jurisdiction=CourtJurisdiction(court_name="12° Juzgado Civil", city="Santiago"))
    return Pagare(**{**base, **kw})


def ledger_for(p: Pagare, cutoff=date(2024, 2, 29)):
    from tests.test_calculator import TABLE
    return calculate_day_by_day_ledger(LiquidationParams(
        principal=p.amount, currency=p.currency, issue_date=p.issue_date,
        maturity_date=p.maturity_date, cutoff_date=cutoff,
        agreed_rate=p.agreed_rate_annual, day_count=DayCount.ACT_365), TABLE)


def text_of(data: bytes) -> str:
    d = Document(BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    parts += [c.text for t in d.tables for r in t.rows for c in r.cells]
    return "\n".join(parts)


def test_formatters():
    assert fmt_clp(D(1_023_836)) == "$1.023.836"
    assert fmt_uf(D("100.1370")) == "100,1370 UF"
    assert fmt_date(date(2024, 2, 9)) == "9 de febrero de 2024"


def test_docx_content_and_typography():
    p = pagare()
    led = ledger_for(p)  # 38,795 interest (see test_calculator)
    data = generate_lawsuit_docx(p, led, ATT)
    doc = Document(BytesIO(data))
    txt = text_of(data)
    for needle in ("BORRADOR", "S.J.L. EN LO CIVIL DE SANTIAGO", "HECHOS", "DERECHO",
                   "PETITORIO", "PRIMER OTROSÍ", "SEGUNDO OTROSÍ", "TERCER OTROSÍ: Patrocinio",
                   "$1.000.000", "$38.795", "$1.038.795", "ANEXO", "María Soto"):
        assert needle in txt, needle
    assert "Acredita personería" not in txt  # no representatives -> omitted
    normal = doc.styles["Normal"]
    assert normal.font.name == "Times New Roman" and normal.font.size.pt == 12
    assert normal.paragraph_format.line_spacing == 1.5
    assert len(doc.tables[0].rows) == 1 + len(led.months)


def test_personeria_otrosi_when_representatives_exist():
    p = pagare(creditor_representatives=[{**PARTY_D, "capacity": "gerente general"}])
    blocks = build_lawsuit(p, ledger_for(p), ATT)
    heads = [b.text for b in blocks if b.kind == "heading"]
    assert any(h.startswith("TERCER OTROSÍ: Acredita personería") for h in heads)
    assert any(h.startswith("CUARTO OTROSÍ: Patrocinio") for h in heads)


def test_jurisdiction_required():
    p = pagare(jurisdiction=None)
    with pytest.raises(ValueError):
        build_lawsuit(p, ledger_for(p), ATT)


def test_uf_instrument_states_both_currencies():
    p = pagare(amount=D(100), currency=Currency.UF, issue_date=date(2024, 2, 10),
               maturity_date=date(2024, 2, 10), agreed_rate_annual=None)
    led = ledger_for(p, cutoff=date(2024, 2, 20))
    txt = text_of(generate_lawsuit_docx(p, led, ATT))
    assert "100,0000 UF" in txt and "0,1370 UF" in txt


# --- procedural wording ---
from app.schemas.instrument import FacturaElectronica


def doc_text(blocks) -> str:
    return "\n".join(b.text for b in blocks)


def factura():
    return FacturaElectronica(
        folio="77", net_amount=D(100_000), vat_amount=D(19_000), total_amount=D(119_000),
        issue_date=date(2024, 1, 1), due_date=date(2024, 1, 31), creditor=PARTY_C, debtor=PARTY_D,
        jurisdiction=CourtJurisdiction(court_name="12° Juzgado Civil", city="Santiago"))


def factura_ledger(f):
    from tests.test_calculator import TABLE
    return calculate_day_by_day_ledger(LiquidationParams(
        principal=f.total_amount, currency=Currency.CLP, issue_date=f.issue_date,
        maturity_date=f.due_date, cutoff_date=date(2024, 2, 29), day_count=DayCount.ACT_365), TABLE)


def test_suma_standard_format():
    p = pagare()
    suma = next(b.text for b in build_lawsuit(p, ledger_for(p), ATT) if b.kind == "suma")
    assert suma == ("EN LO PRINCIPAL: Demanda ejecutiva y mandamiento de ejecución y embargo; "
                    "PRIMER OTROSÍ: Acompaña pagaré en custodia; SEGUNDO OTROSÍ: Señala bienes "
                    "para la traba del embargo; TERCER OTROSÍ: Patrocinio y poder.")


def test_suma_with_personeria():
    p = pagare(creditor_representatives=[{**PARTY_D, "capacity": "gerente"}])
    suma = next(b.text for b in build_lawsuit(p, ledger_for(p), ATT) if b.kind == "suma")
    assert suma.endswith("TERCER OTROSÍ: Acredita personería; CUARTO OTROSÍ: Patrocinio y poder.")


def test_citations_are_strict_per_instrument():
    p = pagare()
    txt = doc_text(build_lawsuit(p, ledger_for(p), ATT))
    assert "artículo 434 N° 4 del Código de Procedimiento Civil y Ley N° 18.092" in txt
    assert "N° 7" not in txt and "19.983" not in txt and " o N° " not in txt
    f = factura()
    txt = doc_text(build_lawsuit(f, factura_ledger(f), ATT))
    assert "artículo 434 N° 7 del Código de Procedimiento Civil y Ley N° 19.983" in txt
    assert "N° 4" not in txt and "18.092" not in txt


def test_compensatory_vs_moratory_interest_split():
    # issue 01-01, maturity 01-31, agreed 24%, ACT/365: Jan 1-31 -> 30d = 19,726.03 -> 19,726 ;
    # total 38,794.52 -> 38,795 ; moratory = 19,069
    p = pagare()
    txt = doc_text(build_lawsuit(p, ledger_for(p), ATT))
    assert "intereses compensatorios (desde la emisión hasta el vencimiento) por $19.726" in txt
    assert "intereses moratorios (desde la fecha de mora hasta el pago efectivo) por $19.069" in txt
    assert "$38.795" in txt and "en mora desde el 1 de febrero de 2024" in txt


def test_no_compensatory_interest_without_agreed_rate():
    p = pagare(agreed_rate_annual=None)
    txt = doc_text(build_lawsuit(p, ledger_for(p), ATT))
    assert "compensatorios" not in txt and "intereses moratorios" in txt


def test_patrocinio_designated_by_creditor_not_self_appointed():
    p = pagare(creditor_representatives=[{**PARTY_D, "capacity": "gerente general"}])
    blocks = build_lawsuit(p, ledger_for(p), ATT)
    txt = doc_text(blocks)
    patro = next(b.text for b in blocks if "designa abogado patrocinante" in b.text)
    assert "designa abogado patrocinante y confiere poder a don(ña) María Soto" in patro
    assert "representada legalmente por Juan Pérez, RUT 12.345.678-5, gerente general" in patro
    assert "Ley N° 18.120" in patro and "designo" not in txt and "confiero" not in txt
    assert not any(b.text.startswith("María Soto, abogado") for b in blocks)


def test_lawsuit_with_payments_states_abonos_and_outstanding():
    from app.schemas.liquidation import Payment
    from tests.test_calculator import TABLE
    p = pagare(agreed_rate_annual=None)
    led = calculate_day_by_day_ledger(LiquidationParams(
        principal=p.amount, currency=p.currency, issue_date=p.issue_date, maturity_date=p.maturity_date,
        cutoff_date=date(2024, 2, 10), day_count=DayCount.ACT_365,
        payments=(Payment(date=date(2024, 2, 10), amount=D(20_000)),)), TABLE)
    txt = doc_text(build_lawsuit(p, led, ATT))
    assert "abonos por un total de $20.000" in txt and "artículo 1595 del Código Civil" in txt
    assert "pagaré por $1.000.000" in txt and "por la suma de $988.219 por concepto de capital" in txt
    assert "compensatorios" not in txt
