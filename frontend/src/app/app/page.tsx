"use client";
import { ArrowLeft, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert } from "@/components/Alert";
import { FileUpload } from "@/components/FileUpload";
import { InstrumentReview } from "@/components/InstrumentReview";
import { LawsuitPreview } from "@/components/LawsuitPreview";
import { LiquidationLedger } from "@/components/LiquidationLedger";
import { CaseSummary } from "@/components/ui/CaseSummary";
import { Logo } from "@/components/ui/Logo";
import { Stepper } from "@/components/ui/Stepper";
import { type Draft, clearDraft, loadDraft, saveDraft } from "@/lib/draft";
import type { Attorney, DayCount, ExtractionResult, Instrument, Ledger, Payment } from "@/lib/types";

const STEPS = ["Ingreso", "Revisión", "Liquidación", "Demanda"];

export default function Workspace() {
  const [step, setStep] = useState(0);
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [cutoff, setCutoff] = useState(new Date().toISOString().slice(0, 10));
  const [dayCount, setDayCount] = useState<DayCount>("ACT/360");
  const [payments, setPayments] = useState<Payment[]>([]);
  const [assets, setAssets] = useState<string[]>([]);
  const [attorney, setAttorney] = useState<Attorney>({ name: "", rut: "", address: "" });
  const [saved, setSaved] = useState<Draft | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const reachable = !instrument ? 0 : !ledger ? 2 : 3;

  useEffect(() => { setSaved(loadDraft()); }, []);

  function restore(d: Draft) {
    setInstrument(d.instrument); setAttorney(d.attorney); setCutoff(d.cutoff); setDayCount(d.dayCount);
    setPayments(d.payments); setAssets(d.assets); setMissing([]); setLedger(null); setStep(2); setSaved(null);
  }

  function save() {
    if (!instrument) return;
    saveDraft({ instrument, attorney, cutoff, dayCount, payments, assets });
    setNotice("Borrador guardado solo en este navegador.");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="container-x flex h-16 items-center justify-between">
          <Logo />
          <Link href="/" className="flex items-center gap-1.5 text-sm font-medium text-ink-600 hover:text-ink-900">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Volver al sitio
          </Link>
        </div>
      </header>
      <main className="container-x py-8">
        <div className="no-print mb-8 space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="eyebrow">Espacio de trabajo</p>
              <h1 className="mt-1 text-3xl font-semibold">Liquidación y demanda ejecutiva</h1>
            </div>
            {instrument && (
              <button className="btn-ghost" onClick={save}><Save className="h-4 w-4" aria-hidden />Guardar borrador en este navegador</button>
            )}
          </div>
          {saved && step === 0 && (
            <Alert kind="warn">
              <div className="flex flex-wrap items-center gap-3">
                <span>Hay un borrador guardado en este navegador ({new Date(saved.savedAt).toLocaleString("es-CL")}).</span>
                <button className="btn-ghost !py-1" onClick={() => restore(saved)}>Restaurar</button>
                <button className="btn-ghost !py-1" onClick={() => { clearDraft(); setSaved(null); }}><Trash2 className="h-3.5 w-3.5" aria-hidden />Descartar</button>
              </div>
            </Alert>
          )}
          {notice && <p role="status" className="text-sm text-ink-600">{notice}</p>}
          <Stepper steps={STEPS} current={step} reachable={reachable} onGo={setStep} />
        </div>
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">
            {step === 0 && (
              <FileUpload onExtracted={(r: ExtractionResult) => {
                setInstrument(r.instrument); setMissing(r.missing_fields); setLedger(null); setPayments([]); setStep(1);
              }} />
            )}
            {step === 1 && instrument && (
              <InstrumentReview instrument={instrument} missing={missing} onChange={(i) => { setInstrument(i); setLedger(null); }}
                onBack={() => setStep(0)} onNext={() => setStep(2)} />
            )}
            {step === 2 && instrument && (
              <LiquidationLedger instrument={instrument} cutoff={cutoff} dayCount={dayCount} ledger={ledger}
                payments={payments} onPayments={(p) => { setPayments(p); setLedger(null); }}
                onChange={(i, c, d) => { setInstrument(i); setCutoff(c); setDayCount(d); }}
                onLedger={setLedger} onBack={() => setStep(1)} onNext={() => setStep(3)} />
            )}
            {step === 3 && instrument && ledger && (
              <LawsuitPreview instrument={instrument} ledger={ledger} cutoff={cutoff} dayCount={dayCount} payments={payments}
                attorney={attorney} assets={assets} onAttorney={setAttorney} onInstrument={setInstrument} onAssets={setAssets}
                onBack={() => setStep(2)} />
            )}
          </div>
          <CaseSummary instrument={instrument} ledger={ledger} cutoff={cutoff} />
        </div>
      </main>
    </div>
  );
}
