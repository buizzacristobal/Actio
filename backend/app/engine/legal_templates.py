"""Parametric Chilean executive-lawsuit templates (CPC art. 434 y ss.).

Deterministic text only: every figure comes from the ledger / instrument. The output
is a DRAFT for attorney review; citations must be verified before filing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.schemas.instrument import (
    Attorney,
    Instrument,
    LegalRepresentative,
    Pagare,
    Party,
)
from app.schemas.liquidation import Currency, LiquidationLedger, Phase

BlockKind = Literal["banner", "suma", "heading", "paragraph", "pagebreak"]

BANNER = "BORRADOR — sujeto a revisión y firma del abogado patrocinante"
_MONTHS = ("enero febrero marzo abril mayo junio julio agosto septiembre octubre "
           "noviembre diciembre").split()
_ORDINALS = ["PRIMER", "SEGUNDO", "TERCER", "CUARTO", "QUINTO"]


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    text: str = ""


def fmt_clp(value: Decimal) -> str:
    return "$" + f"{int(value):,}".replace(",", ".")


def fmt_uf(value: Decimal) -> str:
    whole, _, frac = f"{value:.4f}".partition(".")
    return f"{int(whole):,}".replace(",", ".") + f",{frac} UF"


def fmt_pct(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",") + "%"


def fmt_date(d: date) -> str:
    return f"{d.day} de {_MONTHS[d.month - 1]} de {d.year}"


def _person(p: Party) -> str:
    where = ", ".join(x for x in (p.address, p.commune) if x)
    return f"{p.name}, RUT {p.rut}" + (f", domiciliado en {where}" if where else "")


def _title(instr: Instrument) -> tuple[str, str]:
    if isinstance(instr, Pagare):
        return "PAGARÉ", "COBRO DE PAGARÉ"
    return "FACTURA ELECTRÓNICA", "COBRO DE FACTURA"


def _money(instr: Instrument, ledger: LiquidationLedger) -> tuple[str, str]:
    """(capital text, interest text) in the instrument's native currency."""
    if ledger.params.currency is Currency.UF:
        return (f"{fmt_uf(ledger.params.principal)} ({fmt_clp(ledger.principal_clp)} al "
                f"{fmt_date(ledger.params.cutoff_date)})",
                f"{fmt_uf(ledger.interest_native)} ({fmt_clp(ledger.interest_clp)})")
    return fmt_clp(ledger.principal_clp), fmt_clp(ledger.interest_clp)


def _interest_parts(ledger: LiquidationLedger) -> tuple[str | None, str]:
    """(compensatory text or None, moratory text). Compensatory interest exists only when
    interest accrued between issue and maturity (i.e. an agreed rate)."""
    is_uf = ledger.params.currency is Currency.UF
    conv_days = [d for d in ledger.days if d.phase is Phase.CONVENTIONAL]
    step = Decimal("0.0001") if is_uf else Decimal(1)
    conv = conv_days[-1].accrued_interest.quantize(step, ROUND_HALF_UP) if conv_days else Decimal(0)
    mor = ledger.interest_native - conv
    if is_uf:
        uf_cut = (ledger.days[-1].uf_value if ledger.days else None) or Decimal(0)
        conv_clp = (conv * uf_cut).quantize(Decimal(1), ROUND_HALF_UP)
        mor_clp = ledger.interest_clp - conv_clp
        show = lambda n, c: f"{fmt_uf(n)} ({fmt_clp(c)})"
    else:
        conv_clp, mor_clp = conv, mor
        show = lambda n, c: fmt_clp(n)
    return (show(conv, conv_clp) if conv > 0 else None), show(mor, mor_clp)


_COMP = "intereses compensatorios (desde la emisión hasta el vencimiento)"
_MORA = "intereses moratorios (desde la fecha de mora hasta el pago efectivo)"


def _facts(instr: Instrument, ledger: LiquidationLedger) -> list[str]:
    cap, intr = _money(instr, ledger)
    comp, mor = _interest_parts(ledger)
    p = ledger.params
    cname = instr.creditor.name
    out: list[str]
    if isinstance(instr, Pagare):
        rate = (f" pactándose un interés anual de {fmt_pct(instr.agreed_rate_annual)},"
                if instr.agreed_rate_annual is not None else "")
        out = [f"1. Con fecha {fmt_date(instr.issue_date)}, don(ña) {instr.debtor.name} suscribió "
               f"a favor de {cname} un pagaré por {cap},{rate} pagadero el "
               f"{fmt_date(instr.maturity_date)}."]
    else:
        due = fmt_date(instr.due_date) if instr.due_date else fmt_date(p.maturity_date)
        out = [f"1. {cname} emitió la factura electrónica folio N° {instr.folio}, con "
               f"fecha {fmt_date(instr.issue_date)}, a cargo de {instr.debtor.name}, por "
               f"{cap}, con vencimiento el {due}."]
    out.append(f"2. El deudor no ha pagado el título, encontrándose en mora desde el "
               f"{fmt_date(p.maturity_date + timedelta(days=1))}.")
    detail = (f"correspondientes a {_COMP} por {comp} e {_MORA} por {mor}, devengados a esa fecha"
              if comp else f"correspondientes a {_MORA}, devengados a esa fecha")
    out.append(f"3. Según la liquidación que se acompaña (anexo), al {fmt_date(p.cutoff_date)} "
               f"se adeuda por capital {cap} e intereses por un total de {intr}, {detail}, "
               f"sin perjuicio de los intereses moratorios que se devenguen hasta el pago efectivo.")
    return out


def _law(instr: Instrument) -> list[str]:
    base = ["El artículo 434 del Código de Procedimiento Civil confiere mérito ejecutivo a los "
            "títulos señalados en dicha norma; la obligación es líquida, actualmente exigible "
            "y la acción no se encuentra prescrita."]
    if isinstance(instr, Pagare):
        base.append("El pagaré se rige por la Ley N° 18.092 y, en lo pertinente, por las "
                    "reglas de la letra de cambio; su suscripción consta en el título que se "
                    "acompaña (art. 434 N° 4 CPC; arts. 102 y siguientes de la Ley N° 18.092).")
    else:
        base.append("La factura electrónica tiene mérito ejecutivo conforme al artículo 434 "
                    "N° 7 del Código de Procedimiento Civil, en relación con el artículo 5 de "
                    "la Ley N° 19.983, no habiendo sido reclamada dentro de ocho días corridos "
                    "(art. 3) y habiéndose acreditado el recibo de las mercaderías o servicios.")
    base.append("Los intereses se devengan conforme a la Ley N° 18.010, sin exceder la tasa "
                "máxima convencional.")
    return base


def _otrosi_label(i: int) -> str:
    return f"{_ORDINALS[i]} OTROSÍ"


def _citation(instr: Instrument) -> str:
    if isinstance(instr, Pagare):
        return "artículo 434 N° 4 del Código de Procedimiento Civil y Ley N° 18.092"
    return "artículo 434 N° 7 del Código de Procedimiento Civil y Ley N° 19.983"


def build_lawsuit(instr: Instrument, ledger: LiquidationLedger, attorney: Attorney) -> list[Block]:
    if instr.jurisdiction is None:
        raise ValueError("El tribunal competente (jurisdiction) es obligatorio")
    reps: list[LegalRepresentative] = instr.creditor_representatives
    title, _ = _title(instr)
    cap, intr = _money(instr, ledger)
    comp, mor = _interest_parts(ledger)
    cred = instr.creditor
    rep_names = "; ".join(f"{r.name}, RUT {r.rut}, {r.capacity}" for r in reps)
    rep_clause = f", representada legalmente por {rep_names}" if reps else ""

    otrosies: list[tuple[str, list[str]]] = [
        (f"Acompaña {title.lower()} en custodia",
         [f"Solicito a US. tener por acompañado el {title.lower()} que sirve de título "
          f"ejecutivo conforme al {_citation(instr)}, y disponer su custodia en el tribunal, "
          f"junto con la liquidación de la deuda."]),
        ("Señala bienes para la traba del embargo",
         ["Solicito a US. tener presente que, sin perjuicio de lo que se señale en la "
          "oportunidad correspondiente, se designan para la traba del embargo los bienes "
          "que se indicarán por escrito separado."]),
    ]
    if reps:
        otrosies.append(("Acredita personería",
                         [f"Solicito a US. tener presente que {cred.name} actúa representada "
                          f"legalmente por {rep_names}, cuya personería consta en los "
                          f"documentos que se acompañan."]))
    otrosies.append(("Patrocinio y poder",
                     [f"Solicito a US. tener presente que {cred.name}, RUT {cred.rut}"
                      f"{rep_clause}, designa abogado patrocinante y confiere poder a "
                      f"don(ña) {attorney.name}, RUT {attorney.rut}, domiciliado en "
                      f"{attorney.address}"
                      + (f", correo {attorney.email}" if attorney.email else "")
                      + (f" ({attorney.bar_details})" if attorney.bar_details else "")
                      + ", habilitado para el ejercicio de la profesión (Ley N° 18.120), quien "
                        "lo acepta firmando el presente escrito."]))

    suma = ("EN LO PRINCIPAL: Demanda ejecutiva y mandamiento de ejecución y embargo; "
            + "; ".join(f"{_otrosi_label(i)}: {t}" for i, (t, _) in enumerate(otrosies)) + ".")

    interest_petition = (
        f"más {comp} por concepto de {_COMP}, más {mor} por concepto de {_MORA} "
        f"calculados al {fmt_date(ledger.params.cutoff_date)}, más los intereses moratorios "
        f"que se devenguen hasta el pago efectivo"
        if comp else
        f"más {mor} por concepto de {_MORA} calculados al {fmt_date(ledger.params.cutoff_date)}, "
        f"más los intereses moratorios que se devenguen hasta el pago efectivo")

    blocks = [
        Block("banner", BANNER),
        Block("suma", suma),
        Block("heading", f"S.J.L. EN LO CIVIL DE {instr.jurisdiction.city.upper()}"),
        Block("paragraph", f"({instr.jurisdiction.court_name})"),
        Block("paragraph",
              f"{_person(cred)}{rep_clause}, en juicio ejecutivo contra {_person(instr.debtor)}, "
              f"a US. respetuosamente digo:"),
        Block("heading", "EN LO PRINCIPAL: DEMANDA EJECUTIVA Y MANDAMIENTO DE EJECUCIÓN Y EMBARGO"),
        Block("heading", "HECHOS"),
        *[Block("paragraph", t) for t in _facts(instr, ledger)],
        Block("heading", "DERECHO"),
        *[Block("paragraph", t) for t in _law(instr)],
        Block("heading", "PETITORIO"),
        Block("paragraph",
              f"POR TANTO, solicito a US. tener por interpuesta demanda ejecutiva en contra de "
              f"{instr.debtor.name}, acogerla a tramitación y despachar mandamiento de ejecución "
              f"y embargo por la suma de {cap} por concepto de capital, {interest_petition} y las "
              f"costas de la causa; requerir de pago al deudor y, de no pagar, trabar embargo "
              f"sobre bienes suficientes, ordenando seguir adelante la ejecución hasta hacer "
              f"entero y cumplido pago."),
    ]
    for i, (t, paras) in enumerate(otrosies):
        blocks.append(Block("heading", f"{_otrosi_label(i)}: {t}"))
        blocks.extend(Block("paragraph", x) for x in paras)
    blocks.append(Block("paragraph", f"{fmt_date(ledger.params.cutoff_date)}"))
    blocks.append(Block("paragraph", "____________________________\n" + attorney.name))
    return blocks
