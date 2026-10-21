"use client";
import { ArrowLeft, Download, Eye, RefreshCw } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { generateLawsuit, previewLawsuit } from "@/lib/api";
import { fmtClp } from "@/lib/format";
import { normalizeRut } from "@/lib/rut";
import type { Attorney, Block, DayCount, Instrument, Ledger, LawsuitInput, Payment, Preview } from "@/lib/types";
import { Alert } from "./Alert";
import { Field } from "./ui/Field";

interface Props {
  instrument: Instrument;
  ledger: Ledger;
  cutoff: string;
  dayCount: DayCount;
  payments: Payment[];
  attorney: Attorney;
  assets: string[];
  onAttorney: (a: Attorney) => void;
  onInstrument: (i: Instrument) => void;
  onAssets: (a: string[]) => void;
  onBack: () => void;
}

function AutoTextarea({ value, onChange, className, label }: { value: string; onChange: (v: string) => void; className: string; label: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return <textarea ref={ref} aria-label={label} value={value} rows={1} onChange={(e) => onChange(e.target.value)} className={className} />;
}

function Paper({ blocks, onEdit }: { blocks: Block[]; onEdit: (i: number, text: string) => void }) {
  return (
    <div className="rounded-lg border border-line bg-white p-6 shadow-card sm:p-10" aria-label="Vista previa editable del escrito">
      <div className="mx-auto max-w-[44rem] space-y-3 font-serif text-[15px] leading-7">
        {blocks.map((b, i) => {
          if (b.kind === "pagebreak") return <hr key={i} className="my-4 border-dashed" />;
          if (b.kind === "banner") return <p key={i} className="text-center text-sm font-bold text-red-700">{b.text}</p>;
          const bold = b.kind === "suma" || b.kind === "heading";
          return (
            <AutoTextarea key={i} label={`Párrafo ${i}`} value={b.text} onChange={(t) => onEdit(i, t)}
              className={`block w-full resize-none overflow-hidden rounded border border-transparent bg-transparent p-1 text-justify hover:border-line focus:border-gold-500 ${bold ? "font-bold" : ""}`} />
          );
        })}
      </div>
    </div>
  );
}

export function LawsuitPreview({ instrument, ledger, cutoff, dayCount, payments, attorney, assets, onAttorney, onInstrument, onAssets, onBack }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [edited, setEdited] = useState(false);
  const [snapshot, setSnapshot] = useState("");
  const court = instrument.jurisdiction ?? { court_name: "", city: "" };
  const att = (patch: Partial<Attorney>) => onAttorney({ ...attorney, ...patch });
  const rutBad = attorney.rut.trim() !== "" && !normalizeRut(attorney.rut);

  const input = (): LawsuitInput | null => {
    const rut = normalizeRut(attorney.rut);
    if (!attorney.name.trim() || !attorney.address.trim()) { setError("Complete nombre y domicilio del abogado."); return null; }
    if (!rut) { setError("RUT del abogado inválido (verifique el dígito verificador)."); return null; }
    if (!court.court_name.trim() || !court.city.trim()) { setError("Indique el tribunal y la ciudad."); return null; }
    setError(null);
    return {
      instrument, cutoff_date: cutoff, day_count: dayCount, payments: payments.filter((p) => p.date && Number(p.amount) > 0),
      assets: assets.map((a) => a.trim()).filter(Boolean),
      attorney: { ...attorney, rut, email: attorney.email || undefined, bar_details: attorney.bar_details || undefined },
    };
  };
  const sig = () => JSON.stringify({ attorney, court, assets, instrument: instrument.creditor });
  const stale = preview !== null && snapshot !== sig();

  async function buildPreview() {
    const body = input();
    if (!body) return;
    setBusy("preview");
    try {
      const p = await previewLawsuit(body);
      setPreview(p); setBlocks(p.blocks); setEdited(false); setSnapshot(sig());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally { setBusy(null); }
  }

  async function download(format: "docx" | "pdf") {
    const body = input();
    if (!body) return;
    setBusy(format);
    try {
      const blob = await generateLawsuit({ ...body, edited_blocks: edited ? blocks : undefined }, format);
      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement("a"), { href: url, download: `demanda_ejecutiva.${format}` }).click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally { setBusy(null); }
  }

  return (
    <section className="card space-y-6">
      <div>
        <h2 className="text-xl font-semibold">4. Demanda ejecutiva</h2>
        <p className="mt-1 text-sm text-ink-600">Complete los datos, genere la vista previa, edite el texto si lo desea y descargue el borrador.</p>
      </div>
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold">Abogado patrocinante</legend>
        <Field label="Nombre completo" value={attorney.name} onChange={(e) => att({ name: e.target.value })} />
        <Field label="RUT" value={attorney.rut} placeholder="11.111.111-1" error={rutBad ? "Dígito verificador inválido." : undefined} onChange={(e) => att({ rut: e.target.value })} />
        <Field label="Domicilio" value={attorney.address} onChange={(e) => att({ address: e.target.value })} />
        <Field label="Correo (opcional)" type="email" value={attorney.email ?? ""} onChange={(e) => att({ email: e.target.value })} />
        <Field wide label="Colegio / registro profesional (opcional)" value={attorney.bar_details ?? ""} onChange={(e) => att({ bar_details: e.target.value })} />
      </fieldset>
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold">Tribunal competente</legend>
        <Field label="Tribunal" value={court.court_name} placeholder="12° Juzgado Civil de Santiago"
          onChange={(e) => onInstrument({ ...instrument, jurisdiction: { ...court, court_name: e.target.value } })} />
        <Field label="Ciudad" value={court.city} onChange={(e) => onInstrument({ ...instrument, jurisdiction: { ...court, city: e.target.value } })} />
      </fieldset>
      <div>
        <label htmlFor="assets" className="label">Bienes a embargar (uno por línea, opcional)</label>
        <textarea id="assets" className="input h-24" value={assets.join("\n")} placeholder={"Vehículo PPU ABCD12\nCuenta corriente Banco X"}
          onChange={(e) => onAssets(e.target.value.split("\n"))} />
      </div>
      <div className="rounded-lg border border-line bg-paper p-4 text-sm">
        Monto demandado al {cutoff}: <strong>{fmtClp(ledger.total_clp)}</strong> ({ledger.day_count})
      </div>
      <button className="btn" disabled={busy !== null} onClick={buildPreview}>
        {preview ? <RefreshCw className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
        {busy === "preview" ? "Generando…" : preview ? "Actualizar vista previa" : "Generar vista previa"}
      </button>
      {error && <Alert>{error}</Alert>}

      {preview && (
        <div className="space-y-4 border-t border-line pt-6">
          {stale && <Alert kind="warn">Los datos cambiaron. Actualice la vista previa (se descartarán sus ediciones).</Alert>}
          {preview.notes.length > 0 && (
            <Alert kind="warn">
              <p className="mb-1 font-semibold">Notas para el abogado</p>
              <ul className="list-disc space-y-1 pl-5">{preview.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </Alert>
          )}
          <p className="text-xs text-ink-500">Puede editar cualquier párrafo. La liquidación del anexo siempre se recalcula en el servidor y no es editable.</p>
          <Paper blocks={blocks} onEdit={(i, text) => { setEdited(true); setBlocks(blocks.map((b, k) => (k === i ? { ...b, text } : b))); }} />
        </div>
      )}
      <Alert kind="warn">Borrador sujeto a revisión y firma del abogado. El sistema no presenta nada en la OJV.</Alert>
      <div className="flex flex-wrap gap-3 border-t border-line pt-5">
        <button className="btn-ghost" onClick={onBack}><ArrowLeft className="h-4 w-4" aria-hidden />Volver</button>
        <button className="btn-gold" disabled={busy !== null || !preview || stale} onClick={() => download("docx")}>
          <Download className="h-4 w-4" aria-hidden />{busy === "docx" ? "Generando…" : "Descargar Demanda (.docx)"}
        </button>
        <button className="btn-ghost" disabled={busy !== null || !preview || stale} onClick={() => download("pdf")}>
          <Download className="h-4 w-4" aria-hidden />{busy === "pdf" ? "Generando…" : "Descargar PDF"}
        </button>
      </div>
    </section>
  );
}
