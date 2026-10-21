import type {
  DayCount, ExtractionResult, Instrument, LawsuitInput, Ledger, LiquidationParams, Payment, Preview,
} from "./types";

const BASE = ""; // same-origin: requests go through the Next.js server proxy (src/app/api/v1)

export class ApiError extends Error {}

async function request(path: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, { method: "POST", ...init });
  } catch {
    throw new ApiError("No se pudo conectar con el servidor. ¿Está en ejecución el backend?");
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail))
        msg = j.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
    } catch { /* keep default */ }
    throw new ApiError(msg);
  }
  return res;
}

const post = (path: string, body: unknown) =>
  request(path, { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export async function extract(text: string): Promise<ExtractionResult> {
  return (await (await post("/extract", { text })).json()) as ExtractionResult;
}

export async function extractFile(file: File): Promise<ExtractionResult> {
  const form = new FormData();
  form.append("file", file);
  return (await (await request("/extract-file", { body: form })).json()) as ExtractionResult;
}

export async function liquidate(params: LiquidationParams): Promise<Ledger> {
  return (await (await post("/liquidate", params)).json()) as Ledger;
}

export async function previewLawsuit(input: LawsuitInput): Promise<Preview> {
  return (await (await post("/preview-lawsuit", input)).json()) as Preview;
}

export async function generateLawsuit(input: LawsuitInput, format: "docx" | "pdf"): Promise<Blob> {
  return (await post("/generate-lawsuit", { ...input, format })).blob();
}

export function paramsOf(i: Instrument, cutoff: string, dayCount: DayCount, payments: Payment[] = []): LiquidationParams {
  const pay = payments.filter((p) => p.date && Number(p.amount) > 0);
  if (i.kind === "pagare")
    return {
      principal: i.amount, currency: i.currency, issue_date: i.issue_date, maturity_date: i.maturity_date,
      cutoff_date: cutoff, agreed_rate: i.agreed_rate_annual || null, day_count: dayCount, payments: pay,
    };
  if (!i.due_date) throw new ApiError("La factura requiere fecha de vencimiento (due_date).");
  return {
    principal: i.total_amount, currency: "CLP", issue_date: i.issue_date, maturity_date: i.due_date,
    cutoff_date: cutoff, agreed_rate: null, day_count: dayCount, payments: pay,
  };
}
