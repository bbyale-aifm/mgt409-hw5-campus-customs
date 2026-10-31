import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import DialogueLog from "./components/DialogueLog";
import GoldVault from "./components/GoldVault";
import Party from "./components/Party";
import QuestBoard, { questStatus } from "./components/QuestBoard";
import QuestSummary from "./components/QuestSummary";
import SealModal from "./components/SealModal";
import { buildLog, currentRun, partyState, summaries } from "./party";
import type { Activity, AuditEvent, Cash, PaymentRequest, PriceProposal, Ticket } from "./types";

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [modal, setModal] = useState(false);
  const [flash, setFlash] = useState(0);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const lastSeq = useRef(0);
  const sel = useRef<number | null>(null);

  const refreshBoard = useCallback(async () => {
    try {
      const [t, c] = await Promise.all([api.getTickets(), api.getCash()]);
      setTickets(t);
      setCash(c);
      setError("");
      if (sel.current === null && t.length) {
        const wanted = Number(new URLSearchParams(window.location.search).get("ticket")); // e.g. ?ticket=102
        const first = t.find((x) => x.id === wanted) ?? t[0];
        sel.current = first.id;
        setSelected(first.id);
      }
    } catch {
      setError(`Cannot reach the backend at ${api.API}. Is uvicorn running?`);
    }
  }, []);

  const refreshActivity = useCallback(async () => {
    const id = sel.current;
    if (id === null) return;
    try {
      const a = await api.getActivity(id, lastSeq.current);
      if (sel.current !== id) return; // selection changed while waiting
      setActivity(a);
      if (a.events.length) {
        lastSeq.current = a.events[a.events.length - 1].seq;
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => e.seq)); // overlapping polls can return the same events
          return [...prev, ...a.events.filter((e) => !seen.has(e.seq))];
        });
      }
    } catch {
      /* the board poll shows the connection error */
    }
  }, []);

  const select = (id: number) => {
    sel.current = id;
    lastSeq.current = 0;
    setSelected(id);
    setEvents([]);
    setActivity(null);
    void refreshActivity();
  };

  const running = activity?.run.status === "running";

  useEffect(() => {
    void refreshBoard();
    const t = setInterval(refreshBoard, running ? 1500 : 4000);
    return () => clearInterval(t);
  }, [refreshBoard, running]);

  useEffect(() => {
    void refreshActivity();
    const t = setInterval(refreshActivity, running ? 1000 : 3000);
    return () => clearInterval(t);
  }, [refreshActivity, selected, running]);

  const run = useMemo(() => currentRun(events), [events]);
  const log = useMemo(() => buildLog(run), [run]);
  const party = useMemo(() => partyState(run, !!running), [run, running]);
  const ticket = tickets.find((t) => t.id === selected) ?? null;
  const pending = cash?.pending_requests ?? [];
  const sealCount = pending.length + (cash?.pending_price_proposals.length ?? 0);
  const finished = ticket ? questStatus(ticket) === "completed" : false;
  const cards = useMemo(() => summaries(run), [run]);

  const begin = async () => {
    if (!ticket) return;
    setStarting(true);
    setError("");
    try {
      lastSeq.current = 0;
      setEvents([]);
      await api.runTicket(ticket.id);
      await Promise.all([refreshBoard(), refreshActivity()]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const approve = async (r: PaymentRequest, name: string) => {
    const res = await api.approvePayment(r.id, name);
    setCash((c) => (c ? { ...c, balance: res.new_balance } : c)); // vault updates at once
    setFlash((n) => n + 1);
    await Promise.all([refreshBoard(), refreshActivity()]);
  };
  const approvePrice = async (p: PriceProposal, name: string) => {
    await api.approvePrice(p.id, name);
    await Promise.all([refreshBoard(), refreshActivity()]);
  };
  const rejectPrice = async (p: PriceProposal, name: string) => {
    await api.rejectPrice(p.id, name);
    await Promise.all([refreshBoard(), refreshActivity()]);
  };
  const reject = async (r: PaymentRequest, name: string) => {
    await api.rejectPayment(r.id, name);
    await Promise.all([refreshBoard(), refreshActivity()]);
  };

  const rewind = async () => {
    if (!window.confirm("Rewind the realm? The database returns to its original values and all quests reopen. The audit trail is kept.")) return;
    try {
      await api.resetRealm();
      lastSeq.current = 0;
      setEvents([]);
      setActivity(null);
      setFlash((n) => n + 1);
      await refreshBoard();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Campus <span>Customs</span> Quest Board</h1>
          <p className="muted">The Boss leads the party. The Guild Master (you) holds the Seal.</p>
        </div>
        <GoldVault cash={cash} flash={flash} />
        <div className="top-actions">
          <button className={`btn btn-seal ${sealCount ? "pulse-btn" : ""}`} onClick={() => setModal(true)}>
            🔏 Seals Awaiting {sealCount > 0 && <span className="count">{sealCount}</span>}
          </button>
          <button className="btn btn-ghost" onClick={rewind} disabled={running}>⏪ Rewind the Realm</button>
        </div>
      </header>

      {error && <p className="error banner" role="alert">⚠ {error}</p>}

      <main className="layout">
        <QuestBoard tickets={tickets} selectedId={selected} pending={pending} onSelect={select} />
        <div className="stage">
          {ticket ? (
            <>
              <div className="quest-head">
                <div>
                  <h2 className="quest-title">Quest #{ticket.id}: {ticket.subject}</h2>
                  <p className="muted">{ticket.notes?.split("\n")[0]}</p>
                </div>
                <button className="btn btn-primary" onClick={begin} disabled={running || starting}>
                  {running ? "Quest in progress…" : finished ? "⚔ Run Again" : "⚔ Begin Quest"}
                </button>
              </div>
              {activity?.run.status === "failed" && <p className="error banner" role="alert">☠ The party fell: {activity.run.error}</p>}
              <Party state={party} />
              <DialogueLog lines={log} running={!!running} />
              {finished && cards.length > 0 && !running && (
                <QuestSummary items={cards} title={ticket.subject} sealsPending={pending.filter((p) => p.ticket_id === ticket.id).length} />
              )}
            </>
          ) : (
            <p className="muted">Waiting for the quest board to load…</p>
          )}
        </div>
      </main>

      {modal && cash && <SealModal cash={cash} onClose={() => setModal(false)} onApprove={approve} onReject={reject} onApprovePrice={approvePrice} onRejectPrice={rejectPrice} />}
    </div>
  );
}
