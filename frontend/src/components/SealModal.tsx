import { useEffect, useRef, useState } from "react";
import type { Cash, PaymentRequest, PriceProposal } from "../types";

const fmt = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2 });

interface Props {
  cash: Cash;
  onClose: () => void;
  onApprove: (r: PaymentRequest, name: string) => Promise<void>;
  onReject: (r: PaymentRequest, name: string) => Promise<void>;
  onApprovePrice: (p: PriceProposal, name: string) => Promise<void>;
  onRejectPrice: (p: PriceProposal, name: string) => Promise<void>;
}

export default function SealModal({ cash, onClose, onApprove, onReject, onApprovePrice, onRejectPrice }: Props) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [stamped, setStamped] = useState<number | null>(null);
  const first = useRef<HTMLInputElement>(null);
  const ok = name.trim().length > 0;

  useEffect(() => {
    first.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const act = async <T extends { id: number }>(key: string, r: T, fn: (r: T, name: string) => Promise<void>, seal: boolean) => {
    setBusy(key);
    setError("");
    try {
      await fn(r, name.trim());
      if (seal) setStamped(r.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  let running = cash.balance;
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="seal-h" onClick={(e) => e.stopPropagation()}>
        <h2 id="seal-h">🔏 The Guild Master’s Seal</h2>
        <p className="muted">The party can only <em>prepare</em> payments. Gold leaves the vault only when you stamp the Seal.</p>
        <label className="field">
          Guild Master (your name, recorded with the payment)
          <input ref={first} value={name} onChange={(e) => setName(e.target.value)} placeholder="Type your name" />
        </label>
        {cash.pending_requests.length + cash.pending_price_proposals.length === 0 && <p className="stamped-note">✨ No scrolls await your Seal.{stamped ? " The vault has been updated." : ""}</p>}
        <ul className="seal-list">
          {cash.pending_requests.map((r) => {
            const after = running - r.amount;
            running = after;
            return (
              <li key={r.id} className="seal-item">
                <div>
                  <strong>{r.kind === "rent" ? "Rent to the Castle" : `Vendor invoice #${r.ref_id}`}</strong>
                  <span className="seal-amt">−${fmt(r.amount)}</span>
                  <p className="muted">{r.reason}</p>
                  <p className="seal-after">Vault if every scroll above is sealed: ${fmt(after)} · Quest #{r.ticket_id}</p>
                </div>
                <div className="seal-actions">
                  <button className="btn btn-seal" disabled={!ok || busy !== null} onClick={() => act(`pay${r.id}`, r, onApprove, true)}>
                    {busy === `pay${r.id}` ? "Stamping…" : "Stamp the Seal"}
                  </button>
                  <button className="btn btn-ghost" disabled={!ok || busy !== null} onClick={() => act(`pay${r.id}`, r, onReject, false)}>Deny</button>
                </div>
              </li>
            );
          })}
        </ul>
        {cash.pending_price_proposals.length > 0 && <h3 className="seal-sub">Discount decrees</h3>}
        <ul className="seal-list">
          {cash.pending_price_proposals.map((p) => (
            <li key={`pp${p.id}`} className="seal-item">
              <div>
                <strong>Discount for {p.sku}: ${p.proposed_price.toFixed(2)} each (list ${p.list_price.toFixed(2)})</strong>
                <p className="muted">{p.rationale}</p>
                <p className="seal-after">Margin {p.margin_pct}% · {p.qty} units · Quest #{p.ticket_id} · no gold leaves the vault</p>
              </div>
              <div className="seal-actions">
                <button className="btn btn-seal" disabled={!ok || busy !== null} onClick={() => act(`pp${p.id}`, p, onApprovePrice, true)}>
                  {busy === `pp${p.id}` ? "Stamping…" : "Stamp the Seal"}
                </button>
                <button className="btn btn-ghost" disabled={!ok || busy !== null} onClick={() => act(`pp${p.id}`, p, onRejectPrice, false)}>Deny</button>
              </div>
            </li>
          ))}
        </ul>
        {!ok && cash.pending_requests.length + cash.pending_price_proposals.length > 0 && <p className="hint">Enter your name to unlock the Seal.</p>}
        {error && <p className="error" role="alert">⚠ {error}</p>}
        <div className="modal-foot"><button className="btn btn-ghost" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}
