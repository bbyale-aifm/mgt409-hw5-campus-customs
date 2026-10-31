import type { AuditEvent } from "./types";

export interface Character {
  id: string;
  name: string;
  role: string;
  icon: string;
  blurb: string;
}

export const BOSS: Character = {
  id: "boss", name: "The Boss", role: "Main Player", icon: "👑", blurb: "Leads the party and decides who acts.",
};

export const NPCS: Character[] = [
  { id: "inventory", name: "Merchant", role: "Inventory NPC", icon: "🎒", blurb: "Counts the stockroom, haggles with vendors." },
  { id: "accounting", name: "Treasury Mage", role: "Accounting NPC", icon: "🔮", blurb: "Reads the ledgers, prepares payments for the Seal." },
  { id: "facilities", name: "Castle Steward", role: "Facilities NPC", icon: "🏰", blurb: "Keeps the keep: leases and rent dates." },
  { id: "customer_service", name: "Town Herald", role: "Customer Service NPC", icon: "📯", blurb: "Drafts replies. Never sends them." },
];

export const ALL: Character[] = [BOSS, ...NPCS];
export const who = (id: string): Character =>
  ALL.find((c) => c.id === id) ?? { id, name: id === "human" ? "Guild Master" : id, role: "", icon: "🧙", blurb: "" };

const SPELLS: Record<string, string> = {
  get_ticket: "unrolls the quest scroll",
  get_today: "checks the realm calendar",
  check_stock: "peers into the stockroom",
  list_inventory: "walks every shelf",
  list_vendors: "consults the vendor guild",
  list_invoices: "opens the ledger of debts",
  get_cash_balance: "weighs the Gold Vault",
  get_lease: "reads the castle lease",
  get_pricing: "studies the price runes",
  check_discount: "tests the discount rune",
  list_payment_requests: "checks the Seal queue",
  list_restock_requests: "checks the supply orders",
  list_message_drafts: "checks the herald's drafts",
  create_restock_request: "scribes a restock plea",
  request_payment: "prepares a payment for the Guild Master's Seal",
  propose_price_override: "drafts a discount decree",
  draft_customer_message: "pens a letter (to stay unsent)",
  update_ticket: "updates the quest log",
  list_payments: "reads the paid-gold ledger",
};
export const spell = (tool: string) => SPELLS[tool] ?? `uses ${tool}`;

export type LineKind = "start" | "speech" | "action" | "result" | "report" | "error";
export interface LogLine {
  seq: number;
  agent: string;
  to?: string;
  kind: LineKind;
  text: string;
  tool?: string;
}

const HIDDEN_TOOLS = new Set(["delegate", "hand_off", "final_result"]);
const clip = (s: string, n = 220) => (s.length > n ? `${s.slice(0, n)}…` : s);
const str = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v));

/** The latest quest: from the last main Boss run_start onward, so a later follow-up pass (after the humans decide) is part of it. */
export function currentRun(events: AuditEvent[]): AuditEvent[] {
  let start = -1;
  events.forEach((e, i) => {
    if (e.agent === "boss" && e.event === "run_start" && !String(e.prompt ?? "").startsWith("Follow-up")) start = i;
  });
  return start < 0 ? [] : events.slice(start).filter((e) => e.agent !== "system" && e.agent !== "human");
}

export function buildLog(run: AuditEvent[]): LogLine[] {
  const out: LogLine[] = [];
  for (const e of run) {
    const base = { seq: e.seq, agent: e.agent };
    if (e.event === "run_start" && e.agent === "boss")
      out.push({ ...base, kind: "start", text: String(e.prompt ?? "").startsWith("Follow-up") ? "The Guild Master has ruled. Closing the quest log." : "Quest accepted. Gathering the party." });
    else if (e.event === "delegation" || e.event === "handoff")
      out.push({ ...base, to: String(e.to), kind: "speech", text: `${str(e.task)}` });
    else if (e.event === "agent_note") out.push({ ...base, kind: "speech", text: clip(str(e.text)) });
    else if (e.event === "tool_call" && !HIDDEN_TOOLS.has(String(e.tool)))
      out.push({ ...base, kind: "action", tool: String(e.tool), text: `${spell(String(e.tool))}`, });
    else if (e.event === "tool_result" && !HIDDEN_TOOLS.has(String(e.tool)))
      out.push({ ...base, kind: "result", tool: String(e.tool), text: clip(str(e.result), 260) });
    else if (e.event === "agent_output") out.push({ ...base, kind: "report", text: reportText(e) });
    else if (e.event === "error") out.push({ ...base, kind: "error", text: str(e.error) });
  }
  return out;
}

function reportText(e: AuditEvent): string {
  const o = (e.output ?? {}) as Record<string, unknown>;
  return str(o.summary ?? o.recommendation ?? "Report delivered.");
}

export interface CharState {
  active: boolean;
  done: boolean;
  lastTool?: string;
  actions: number;
}

/** Who is acting now (top of the run_start/run_end stack) and what each character has done. */
export function partyState(run: AuditEvent[], running: boolean): Record<string, CharState> {
  const st: Record<string, CharState> = {};
  ALL.forEach((c) => (st[c.id] = { active: false, done: false, actions: 0 }));
  const stack: string[] = [];
  for (const e of run) {
    const c = st[e.agent];
    if (!c) continue;
    if (e.event === "run_start") stack.push(e.agent);
    else if (e.event === "run_end") {
      stack.pop();
      c.done = true;
    } else if (e.event === "tool_call" && !HIDDEN_TOOLS.has(String(e.tool))) {
      c.actions += 1;
      c.lastTool = String(e.tool);
    }
  }
  const top = stack[stack.length - 1];
  if (running && top) st[top].active = true;
  return st;
}

export interface Summary {
  agent: string;
  text: string;
  findings: string[];
  actions: string[];
  approvals: string[];
}

/** One end-of-quest card per character, from their last structured report. */
export function summaries(run: AuditEvent[]): Summary[] {
  const last: Record<string, AuditEvent> = {};
  run.filter((e) => e.event === "agent_output").forEach((e) => (last[e.agent] = e));
  return ALL.filter((c) => last[c.id]).map((c) => {
    const o = (last[c.id].output ?? {}) as Record<string, unknown>;
    const list = (k: string) => (Array.isArray(o[k]) ? (o[k] as unknown[]).map(str) : []);
    return {
      agent: c.id,
      text: str(o.summary ?? o.recommendation ?? ""),
      findings: c.id === "boss" ? list("delegations") : list("findings"),
      actions: c.id === "boss" ? list("drafts_saved") : list("actions_taken"),
      approvals: c.id === "boss" ? list("pending_human_approvals") : list("needs_human_approval"),
    };
  });
}
