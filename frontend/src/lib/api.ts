import type { Attorney, DayCount, Instrument, Ledger, LiquidationParams } from "./types";

const BASE = ""; // same-origin: requests go through the Next.js server proxy (src/app/api/v1)

export class ApiError extends Error {}

async function post(path: string, body: unknown): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
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

export async function extract(text: string): Promise<Instrument> {
  return (await (await post("/extract", { text })).json()).instrument as Instrument;
}

export async function liquidate(params: LiquidationParams): Promise<Ledger> {
  return (await (await post("/liquidate", params)).json()) as Ledger;
}

export async function generateLawsuit(
  instrument: Instrument, attorney: Attorney, cutoff_date: string, day_count: DayCount,
): Promise<Blob> {
  return (await post("/generate-lawsuit", { instrument, attorney, cutoff_date, day_count })).blob();
}

export function paramsOf(i: Instrument, cutoff: string, dayCount: DayCount): LiquidationParams {
  if (i.kind === "pagare")
    return {
      principal: i.amount, currency: i.currency, issue_date: i.issue_date, maturity_date: i.maturity_date,
      cutoff_date: cutoff, agreed_rate: i.agreed_rate_annual || null, day_count: dayCount,
    };
  if (!i.due_date) throw new ApiError("La factura requiere fecha de vencimiento (due_date).");
  return {
    principal: i.total_amount, currency: "CLP", issue_date: i.issue_date, maturity_date: i.due_date,
    cutoff_date: cutoff, agreed_rate: null, day_count: dayCount,
  };
}
