export type RunStatus = "idle" | "running" | "finished" | "failed";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  status: string;
  notes: string | null;
  state: "open" | "resolved";
  run_status: RunStatus;
}

export interface AuditEvent {
  seq: number;
  timestamp: string;
  ticket_id: number | null;
  agent: string;
  event: string;
  [key: string]: unknown;
}

export interface PaymentRequest {
  id: number;
  kind: "invoice" | "rent";
  ref_id: number;
  amount: number;
  reason: string | null;
  ticket_id: number | null;
  status: string;
}

export interface PriceProposal {
  id: number;
  ticket_id: number;
  sku: string;
  qty: number | null;
  list_price: number;
  proposed_price: number;
  margin_pct: number;
  rationale: string | null;
  status: string;
}

export interface Records {
  payment_requests: PaymentRequest[];
  restock_requests: Record<string, unknown>[];
  message_drafts: { id: number; recipient: string; subject: string; body: string }[];
  price_proposals: Record<string, unknown>[];
}

export interface Activity {
  ticket: Ticket;
  run: { status: RunStatus; error?: string; outcome?: Record<string, unknown>; tokens?: number };
  events: AuditEvent[];
  records: Records;
}

export interface Cash {
  balance: number;
  pending_requests_total: number;
  available_after_pending: number;
  pending_requests: PaymentRequest[];
  pending_price_proposals: PriceProposal[];
  payments: { id: number; kind: string; amount: number; approved_by: string }[];
}
