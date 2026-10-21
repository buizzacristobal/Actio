// Drafts live only in this browser's localStorage; nothing is sent to a server.
import type { Attorney, DayCount, Instrument, Payment } from "./types";

const KEY = "legaltech-chile-draft-v1";

export interface Draft {
  instrument: Instrument;
  attorney: Attorney;
  cutoff: string;
  dayCount: DayCount;
  payments: Payment[];
  assets: string[];
  savedAt: string;
}

export function saveDraft(d: Omit<Draft, "savedAt">): void {
  try { localStorage.setItem(KEY, JSON.stringify({ ...d, savedAt: new Date().toISOString() })); } catch { /* storage unavailable */ }
}

export function loadDraft(): Draft | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch { return null; }
}

export function clearDraft(): void {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
