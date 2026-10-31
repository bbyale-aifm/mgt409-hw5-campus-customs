import type { PaymentRequest, Ticket } from "../types";

const TITLES: Record<string, string> = {
  customer_order: "The Missing Tee",
  rent_notice: "The Landlord's Summons",
  price_override: "The Club's Bulk Bargain",
};

export type QuestStatus = "open" | "active" | "completed" | "failed";

export function questStatus(t: Ticket): QuestStatus {
  if (t.run_status === "running") return "active";
  if (t.run_status === "failed") return "failed";
  if (t.run_status === "finished" || t.state === "resolved" || t.status === "waiting_approval") return "completed";
  return "open";
}

const LABEL: Record<QuestStatus, string> = { open: "Open", active: "In Progress", completed: "Completed", failed: "Quest Failed" };

interface Props {
  tickets: Ticket[];
  selectedId: number | null;
  pending: PaymentRequest[];
  onSelect: (id: number) => void;
}

export default function QuestBoard({ tickets, selectedId, pending, onSelect }: Props) {
  return (
    <section aria-labelledby="board-h" className="board">
      <h2 id="board-h">Quest Board</h2>
      <ul className="scrolls">
        {tickets.map((t) => {
          const s = questStatus(t);
          const seals = pending.filter((p) => p.ticket_id === t.id).length;
          return (
            <li key={t.id}>
              <button className={`scroll ${selectedId === t.id ? "selected" : ""} st-${s}`} aria-pressed={selectedId === t.id} onClick={() => onSelect(t.id)}>
                <span className="scroll-top">
                  <span className="quest-no">Quest #{t.id}</span>
                  <span className={`badge badge-${s}`}>{LABEL[s]}</span>
                </span>
                <span className="scroll-title">{TITLES[t.type] ?? t.subject}</span>
                <span className="scroll-sub">{t.requester} · {t.subject}{t.size ? ` (${t.size}, ×${t.qty})` : ""}</span>
                <span className="scroll-type">{t.type.replace("_", " ")}</span>
                {seals > 0 && <span className="seal-chip">🔏 {seals} seal{seals > 1 ? "s" : ""} awaited</span>}
              </button>
            </li>
          );
        })}
        {tickets.length === 0 && <li className="muted">No quests posted yet…</li>}
      </ul>
    </section>
  );
}
