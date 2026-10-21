export type Currency = "CLP" | "UF";
export type DayCount = "ACT/360" | "ACT/365";

export interface Party { name: string; rut: string; address?: string | null; commune?: string | null }
export interface Representative extends Party { capacity: string }
export interface Jurisdiction { court_name: string; city: string }

interface Base {
  creditor: Party;
  debtor: Party;
  creditor_representatives?: Representative[];
  debtor_representatives?: Representative[];
  jurisdiction?: Jurisdiction | null;
}
export interface Pagare extends Base {
  kind: "pagare";
  amount: string;
  currency: Currency;
  issue_date: string;
  maturity_date: string;
  agreed_rate_annual?: string | null;
  guarantors?: Party[];
  signature_authorized?: boolean | null;
}
export interface Factura extends Base {
  kind: "factura";
  folio: string;
  net_amount: string;
  vat_amount: string;
  total_amount: string;
  currency?: "CLP";
  issue_date: string;
  due_date?: string | null;
  receipt_acknowledged?: boolean | null;
}
export type Instrument = Pagare | Factura;

export interface Attorney { name: string; rut: string; address: string; email?: string; bar_details?: string }

export interface LiquidationParams {
  principal: string;
  currency: Currency;
  issue_date: string;
  maturity_date: string;
  cutoff_date: string;
  agreed_rate: string | null;
  day_count: DayCount;
  payments?: Payment[];
}
export interface LedgerDay {
  date: string; phase: "conventional" | "moratory"; annual_rate: string; uf_value: string | null;
  readjustment_factor: string | null; capital: string; capital_clp: string;
  daily_interest: string; accrued_interest: string; payment: string; capital_end: string; interest_due: string;
}
export interface LedgerMonth {
  period: string; days: number; annual_rate: string; capital: string; interest: string;
  accrued_interest: string; uf_value_end: string | null; accumulated_total_clp: string; payments: string;
}
export interface Ledger {
  params: LiquidationParams; category: string; days: LedgerDay[]; months: LedgerMonth[];
  principal_clp: string; interest_native: string; interest_clp: string; total_clp: string;
  capital_native: string; interest_accrued_native: string; payments_total: string;
  day_count: DayCount; rate_table_verified: boolean; warnings: string[];
}

export interface Payment { date: string; amount: string }
export interface Block { kind: "banner" | "suma" | "heading" | "paragraph" | "pagebreak"; text: string }
export interface Preview { blocks: Block[]; notes: string[]; total_clp: string; warnings: string[] }
export interface ExtractionResult { instrument: Instrument; missing_fields: string[] }
export interface LawsuitInput {
  instrument: Instrument;
  attorney: Attorney;
  cutoff_date: string;
  day_count: DayCount;
  payments: Payment[];
  assets: string[];
  edited_blocks?: Block[];
}
