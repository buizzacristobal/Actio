"use client";
import { ArrowLeft, ArrowRight, Plus, Trash2 } from "lucide-react";
import { normalizeRut } from "@/lib/rut";
import type { Instrument, Party, Representative } from "@/lib/types";
import { Alert } from "./Alert";
import { Field, SelectField } from "./ui/Field";

interface Props {
  instrument: Instrument;
  missing: string[];
  onChange: (i: Instrument) => void;
  onBack: () => void;
  onNext: () => void;
}

const tri = (v: boolean | null | undefined) => (v === true ? "true" : v === false ? "false" : "");
const fromTri = (v: string) => (v === "" ? null : v === "true");
const rutError = (r: string) => (r.trim() && !normalizeRut(r) ? "RUT inválido (dígito verificador)." : undefined);

export function reviewErrors(i: Instrument): string[] {
  const out: string[] = [];
  const chk = (label: string, p: Party) => {
    if (!p.name.trim()) out.push(`${label}: falta el nombre.`);
    if (!normalizeRut(p.rut)) out.push(`${label}: RUT inválido.`);
  };
  chk("Acreedor", i.creditor);
  chk("Deudor", i.debtor);
  (i.creditor_representatives ?? []).forEach((r, n) => {
    if (!r.name.trim() || !r.capacity.trim() || !normalizeRut(r.rut)) out.push(`Representante ${n + 1}: complete nombre, RUT válido y calidad.`);
  });
  return out;
}

function PartyFields({ title, who, p, missing, onChange }: { title: string; who: string; p: Party; missing: string[]; onChange: (p: Party) => void }) {
  const set = (patch: Partial<Party>) => onChange({ ...p, ...patch });
  return (
    <fieldset className="grid gap-4 sm:grid-cols-2">
      <legend className="mb-3 text-sm font-semibold">{title}</legend>
      <Field label="Nombre o razón social" value={p.name} onChange={(e) => set({ name: e.target.value })} />
      <Field label="RUT" value={p.rut} error={rutError(p.rut)} onChange={(e) => set({ rut: e.target.value })} />
      <Field label="Domicilio" value={p.address ?? ""} flag={missing.includes(`${who}.address`)} onChange={(e) => set({ address: e.target.value })} />
      <Field label="Comuna" value={p.commune ?? ""} onChange={(e) => set({ commune: e.target.value })} />
    </fieldset>
  );
}

export function InstrumentReview({ instrument, missing, onChange, onBack, onNext }: Props) {
  const reps: Representative[] = instrument.creditor_representatives ?? [];
  const court = instrument.jurisdiction ?? { court_name: "", city: "" };
  const errors = reviewErrors(instrument);
  const setReps = (r: Representative[]) => onChange({ ...instrument, creditor_representatives: r });

  return (
    <section className="card space-y-7">
      <div>
        <h2 className="text-xl font-semibold">2. Revisión de datos extraídos</h2>
        <p className="mt-1 text-sm text-ink-600">Verifique cada dato contra el documento original. Los campos marcados «Revisar» no se encontraron.</p>
      </div>
      <PartyFields title="Acreedor" who="creditor" p={instrument.creditor} missing={missing} onChange={(creditor) => onChange({ ...instrument, creditor })} />
      <PartyFields title="Deudor" who="debtor" p={instrument.debtor} missing={missing} onChange={(debtor) => onChange({ ...instrument, debtor })} />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-sans text-sm font-semibold tracking-normal">Representantes legales del acreedor</h3>
          <button className="btn-ghost !py-1.5" onClick={() => setReps([...reps, { name: "", rut: "", capacity: "" }])}><Plus className="h-4 w-4" aria-hidden />Agregar</button>
        </div>
        {reps.length === 0 && <p className="text-sm text-ink-500">Sin representantes. Si el acreedor es una persona jurídica, agréguelos para incluir el otrosí «Acredita personería».</p>}
        {reps.map((r, n) => (
          <div key={n} className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
            <Field label="Nombre" value={r.name} onChange={(e) => setReps(reps.map((x, k) => (k === n ? { ...x, name: e.target.value } : x)))} />
            <Field label="RUT" value={r.rut} error={rutError(r.rut)} onChange={(e) => setReps(reps.map((x, k) => (k === n ? { ...x, rut: e.target.value } : x)))} />
            <Field label="Calidad" value={r.capacity} placeholder="gerente general" onChange={(e) => setReps(reps.map((x, k) => (k === n ? { ...x, capacity: e.target.value } : x)))} />
            <button className="btn-ghost" aria-label={`Quitar representante ${n + 1}`} onClick={() => setReps(reps.filter((_, k) => k !== n))}><Trash2 className="h-4 w-4" aria-hidden /></button>
          </div>
        ))}
      </div>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold">{instrument.kind === "pagare" ? "Pagaré" : "Factura electrónica"}</legend>
        {instrument.kind === "pagare" ? (
          <SelectField label="Firma autorizada ante notario" flag={missing.includes("signature_authorized")}
            value={tri(instrument.signature_authorized)} onChange={(e) => onChange({ ...instrument, signature_authorized: fromTri(e.target.value) })}>
            <option value="">No consta</option><option value="true">Sí</option><option value="false">No</option>
          </SelectField>
        ) : (
          <>
            <Field label="Folio" value={instrument.folio} onChange={(e) => onChange({ ...instrument, folio: e.target.value })} />
            <Field label="Vencimiento" type="date" value={instrument.due_date ?? ""} flag={missing.includes("due_date")}
              onChange={(e) => onChange({ ...instrument, due_date: e.target.value || null })} />
            <SelectField label="Acuse de recibo" flag={missing.includes("receipt_acknowledged")}
              value={tri(instrument.receipt_acknowledged)} onChange={(e) => onChange({ ...instrument, receipt_acknowledged: fromTri(e.target.value) })}>
              <option value="">No consta</option><option value="true">Sí</option><option value="false">No</option>
            </SelectField>
          </>
        )}
      </fieldset>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold">Tribunal competente</legend>
        <Field label="Tribunal" value={court.court_name} flag={missing.includes("jurisdiction")} placeholder="12° Juzgado Civil de Santiago"
          onChange={(e) => onChange({ ...instrument, jurisdiction: { ...court, court_name: e.target.value } })} />
        <Field label="Ciudad" value={court.city} flag={missing.includes("jurisdiction")}
          onChange={(e) => onChange({ ...instrument, jurisdiction: { ...court, city: e.target.value } })} />
      </fieldset>

      {errors.length > 0 && <Alert>{errors.map((e) => <div key={e}>{e}</div>)}</Alert>}
      <div className="flex gap-3 border-t border-line pt-5">
        <button className="btn-ghost" onClick={onBack}><ArrowLeft className="h-4 w-4" aria-hidden />Volver</button>
        <button className="btn-gold" disabled={errors.length > 0} onClick={onNext}>Continuar <ArrowRight className="h-4 w-4" aria-hidden /></button>
      </div>
    </section>
  );
}
