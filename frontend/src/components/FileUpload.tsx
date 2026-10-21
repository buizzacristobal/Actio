"use client";
import { FileText, Sparkles, Upload } from "lucide-react";
import { useState } from "react";
import { extract, extractFile } from "@/lib/api";
import { SAMPLE_FACTURA, SAMPLE_FACTURA_TEXT, SAMPLE_PAGARE, SAMPLE_PAGARE_TEXT } from "@/lib/samples";
import type { ExtractionResult, Instrument } from "@/lib/types";
import { Alert } from "./Alert";

const MAX_MB = 10;
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.txt,application/pdf,image/png,image/jpeg,image/webp,text/plain";

export function FileUpload({ onExtracted }: { onExtracted: (r: ExtractionResult) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function guarded(label: string, fn: () => Promise<ExtractionResult>) {
    setBusy(label);
    setError(null);
    try {
      onExtracted(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setBusy(null);
    }
  }

  function pickFile(f: File) {
    if (f.size > MAX_MB * 1024 * 1024) return setError(`El archivo supera ${MAX_MB} MB.`);
    if (/\.txt$/i.test(f.name)) {
      setError(null);
      void f.text().then(setText);
      return;
    }
    void guarded("file", () => extractFile(f));
  }

  const sample = (instrument: Instrument): ExtractionResult => ({ instrument, missing_fields: [] });

  return (
    <section className="card space-y-6">
      <div>
        <h2 className="text-xl font-semibold">1. Ingreso del título</h2>
        <p className="mt-1 text-sm text-ink-600">
          Suba un PDF o una imagen del título, o pegue su texto. La IA transcribe los campos; usted los revisa en el paso siguiente.
        </p>
      </div>
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-line bg-paper px-6 py-8 text-center transition hover:border-gold-400"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) pickFile(f); }}>
        <Upload className="h-6 w-6 text-gold-600" aria-hidden />
        <span className="text-sm font-medium">{busy === "file" ? "Leyendo documento…" : "Arrastre un archivo o haga clic para elegirlo"}</span>
        <span className="text-xs text-ink-500">PDF (con texto o escaneado), PNG, JPG, WEBP o .txt · máx. {MAX_MB} MB · no se almacena</span>
        <input type="file" accept={ACCEPT} className="sr-only" aria-label="Subir documento"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); e.target.value = ""; }} />
      </label>
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="label !mb-0 mr-1">O pegue el texto</span>
          <button className="btn-ghost !py-1.5" onClick={() => setText(SAMPLE_PAGARE_TEXT)}><FileText className="h-4 w-4" aria-hidden />Ejemplo Pagaré</button>
          <button className="btn-ghost !py-1.5" onClick={() => setText(SAMPLE_FACTURA_TEXT)}><FileText className="h-4 w-4" aria-hidden />Ejemplo Factura</button>
        </div>
        <label htmlFor="doc-text" className="sr-only">Texto del título</label>
        <textarea id="doc-text" className="input h-48 font-mono text-[13px] leading-relaxed" value={text}
          onChange={(e) => setText(e.target.value)} placeholder="Pegue aquí el texto del pagaré o factura…" />
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <button className="btn" disabled={busy !== null || !text.trim()} onClick={() => guarded("text", () => extract(text))}>
          <Sparkles className="h-4 w-4" aria-hidden />{busy === "text" ? "Extrayendo…" : "Extraer con IA"}
        </button>
        <span className="text-xs text-ink-500">o continúe sin IA con datos de ejemplo:</span>
        <button className="btn-ghost !py-1.5" onClick={() => onExtracted(sample(SAMPLE_PAGARE))}>Pagaré</button>
        <button className="btn-ghost !py-1.5" onClick={() => onExtracted(sample(SAMPLE_FACTURA))}>Factura</button>
      </div>
    </section>
  );
}
