"use client";
import { ArrowLeft, ArrowRight, Plus, Printer, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { liquidate, paramsOf } from "@/lib/api";
import { CATEGORY_LABEL, fmtClp, fmtMoney, fmtPct, fmtUf } from "@/lib/format";
import type { DayCount, Instrument, Ledger, Payment } from "@/lib/types";
import { Alert } from "./Alert";
import { Field, SelectField } from "./ui/Field";

interface Props {
  instrument: Instrument;
  cutoff: string;
  dayCount: DayCount;
  onChange: (i: Instrument, cutoff: string, dayCount: DayCount) => void;
  onLedger: (l: Ledger | null) => void;
  onBack: () => void;
  onNext: () => void;
  ledger: Ledger | null;
  payments: Payment[];
  onPayments: (p: Payment[]) => void;
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`rounded-lg p-4 ${strong ? "bg-ink-900 text-white" : "bg-paper"}`}>
      <dt className={`text-xs font-semibold uppercase tracking-wide ${strong ? "text-ink-300" : "text-ink-500"}`}>{label}</dt>
      <dd className="mt-1 font-serif text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

export function LiquidationLedger({ instrument, cutoff, dayCount, onChange, onLedger, onBack, onNext, ledger, payments, onPayments }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [daily, setDaily] = useState(false);
  const isPagare = instrument.kind === "pagare";

  async function run() {
    setError(null);
    setBusy(true);
    try {
      const p = paramsOf(instrument, cutoff, dayCount, payments);
      if (p.maturity_date < p.issue_date) throw new Error("El vencimiento es anterior a la emisión.");
      if (p.cutoff_date < p.maturity_date) throw new Error("La fecha de corte es anterior al vencimiento.");
      if (!(Number(p.principal) > 0)) throw new Error("El capital debe ser mayor a cero.");
      for (const x of p.payments ?? [])
        if (x.date <= p.issue_date || x.date > p.cutoff_date) throw new Error(`El abono del ${x.date} debe ser posterior a la emisión y no posterior al corte.`);
      onLedger(await liquidate(p));
    } catch (e) {
      onLedger(null);
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setBusy(false);
    }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void run(); }, []);

  const set = (patch: Record<string, string | null>) => onChange({ ...instrument, ...patch } as Instrument, cutoff, dayCount);
  const cur = ledger?.params.currency ?? "CLP";
  const th = "px-3 py-2 text-right font-semibold first:text-left";

  return (
    <section className="card space-y-6">
      <div>
        <h2 className="text-xl font-semibold">2. Liquidación de la deuda</h2>
        <p className="mt-1 text-sm text-ink-600">Ajuste los parámetros y recalcule. El tramo de tasa se determina por el monto en UF a la fecha de emisión.</p>
      </div>
      <div className="no-print grid gap-4 sm:grid-cols-3">
        {isPagare && (
          <>
            <Field label={`Capital (${instrument.currency})`} value={instrument.amount} inputMode="decimal" onChange={(e) => set({ amount: e.target.value })} />
            <Field label="Emisión" type="date" value={instrument.issue_date} onChange={(e) => set({ issue_date: e.target.value })} />
            <Field label="Vencimiento" type="date" value={instrument.maturity_date} onChange={(e) => set({ maturity_date: e.target.value })} />
            <Field label="Tasa pactada anual %" hint="Opcional. Se topa a la TMC." value={instrument.agreed_rate_annual ?? ""} inputMode="decimal"
              onChange={(e) => set({ agreed_rate_annual: e.target.value || null })} />
          </>
        )}
        <Field label="Fecha de corte" type="date" value={cutoff} onChange={(e) => onChange(instrument, e.target.value, dayCount)} />
        <SelectField label="Base de días" value={dayCount} onChange={(e) => onChange(instrument, cutoff, e.target.value as DayCount)}>
          <option>ACT/360</option><option>ACT/365</option>
        </SelectField>
      </div>
      <fieldset className="no-print space-y-3">
        <div className="flex items-center justify-between">
          <legend className="text-sm font-semibold">Abonos recibidos <span className="font-normal text-ink-500">(se imputan primero a intereses, luego a capital)</span></legend>
          <button className="btn-ghost !py-1.5" onClick={() => onPayments([...payments, { date: "", amount: "" }])}><Plus className="h-4 w-4" aria-hidden />Agregar abono</button>
        </div>
        {payments.map((x, n) => (
          <div key={n} className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <Field label="Fecha del abono" type="date" value={x.date} onChange={(e) => onPayments(payments.map((y, k) => (k === n ? { ...y, date: e.target.value } : y)))} />
            <Field label={`Monto (${cur === "UF" || (isPagare && instrument.currency === "UF") ? "UF" : "CLP"})`} inputMode="decimal" value={x.amount}
              onChange={(e) => onPayments(payments.map((y, k) => (k === n ? { ...y, amount: e.target.value } : y)))} />
            <button className="btn-ghost" aria-label={`Quitar abono ${n + 1}`} onClick={() => onPayments(payments.filter((_, k) => k !== n))}><Trash2 className="h-4 w-4" aria-hidden /></button>
          </div>
        ))}
      </fieldset>
      <button className="btn no-print" disabled={busy} onClick={run}>
        <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} aria-hidden />{busy ? "Calculando…" : "Recalcular"}
      </button>
      {error && <Alert>{error}</Alert>}

      {ledger && (
        <div className="space-y-5 border-t border-line pt-6">
          <div className="space-y-2">{ledger.warnings.map((w) => <Alert key={w} kind="warn">{w}</Alert>)}</div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="badge">{CATEGORY_LABEL[ledger.category] ?? ledger.category}</span>
            <span className="text-xs text-ink-500">Base {ledger.day_count}</span>
          </div>
          <dl className="grid gap-3 sm:grid-cols-3">
            <Stat label={Number(ledger.payments_total) > 0 ? "Capital (saldo)" : "Capital"} value={fmtClp(ledger.principal_clp)} />
            <Stat label="Intereses" value={fmtClp(ledger.interest_clp)} />
            <Stat label="Total" value={fmtClp(ledger.total_clp)} strong />
          </dl>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold">{daily ? "Detalle día por día" : "Detalle mensual"}</h3>
            <div className="no-print flex items-center gap-4">
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" className="accent-gold-500" checked={daily} onChange={(e) => setDaily(e.target.checked)} /> Ver día por día
              </label>
              <button className="btn-ghost !py-1.5" onClick={() => window.print()}><Printer className="h-4 w-4" aria-hidden />Imprimir planilla</button>
            </div>
          </div>
          <div tabIndex={0} role="region" aria-label="Planilla de liquidación" className="max-h-[26rem] overflow-auto rounded-lg border border-line print:max-h-none">
            <table className="w-full text-sm tabular-nums">
              <thead className="sticky top-0 bg-ink-900 text-xs uppercase tracking-wide text-white">
                {daily ? (
                  <tr><th className={th}>Fecha</th><th className={th}>Fase</th><th className={th}>Tasa anual</th>
                    {cur === "UF" && <th className={th}>UF</th>}<th className={th}>Capital</th><th className={th}>Interés del día</th><th className={th}>Acumulado</th></tr>
                ) : (
                  <tr><th className={th}>Período</th><th className={th}>Días</th><th className={th}>Tasa anual</th><th className={th}>Capital</th>
                    <th className={th}>Interés del mes</th><th className={th}>Interés acum.</th><th className={th}>Total acum. ($)</th></tr>
                )}
              </thead>
              <tbody className="[&>tr:nth-child(even)]:bg-paper">
                {daily
                  ? ledger.days.map((d) => (
                    <tr key={d.date} className="border-t border-line/60">
                      <td className="px-3 py-1.5">{d.date}</td><td className="px-3 text-right">{d.phase === "moratory" ? "mora" : "convencional"}</td>
                      <td className="px-3 text-right">{fmtPct(d.annual_rate)}</td>{cur === "UF" && <td className="px-3 text-right">{d.uf_value && fmtClp(d.uf_value)}</td>}
                      <td className="px-3 text-right">{fmtMoney(d.capital, cur)}</td>
                      <td className="px-3 text-right">{Number(d.daily_interest).toFixed(cur === "UF" ? 6 : 2)}</td>
                      <td className="px-3 text-right">{Number(d.accrued_interest).toFixed(cur === "UF" ? 6 : 2)}</td>
                    </tr>))
                  : ledger.months.map((m) => (
                    <tr key={m.period} className="border-t border-line/60">
                      <td className="px-3 py-2">{m.period}</td><td className="px-3 text-right">{m.days}</td><td className="px-3 text-right">{fmtPct(m.annual_rate)}</td>
                      <td className="px-3 text-right">{fmtMoney(m.capital, cur)}</td><td className="px-3 text-right">{fmtMoney(m.interest, cur)}</td>
                      <td className="px-3 text-right">{fmtMoney(m.accrued_interest, cur)}</td><td className="px-3 text-right font-medium">{fmtClp(m.accumulated_total_clp)}</td>
                    </tr>))}
              </tbody>
            </table>
          </div>
          {cur === "UF" && <p className="text-xs text-ink-500">Capital {fmtUf(ledger.params.principal)}; montos en UF, equivalente en $ al corte.</p>}
        </div>
      )}
      <div className="no-print flex gap-3 border-t border-line pt-5">
        <button className="btn-ghost" onClick={onBack}><ArrowLeft className="h-4 w-4" aria-hidden />Volver</button>
        <button className="btn-gold" disabled={!ledger} onClick={onNext}>Continuar <ArrowRight className="h-4 w-4" aria-hidden /></button>
      </div>
    </section>
  );
}
