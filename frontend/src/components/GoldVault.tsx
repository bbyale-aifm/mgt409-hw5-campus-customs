import { useEffect, useRef, useState } from "react";
import type { Cash } from "../types";

const fmt = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function GoldVault({ cash, flash }: { cash: Cash | null; flash: number }) {
  const target = cash?.balance ?? 0;
  const [shown, setShown] = useState(target);
  const from = useRef(target);

  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 900);
      const v = a + (target - a) * (1 - Math.pow(1 - p, 3));
      setShown(v);
      from.current = v;
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return (
    <div className={`vault ${flash ? "vault-flash" : ""}`} key={flash} aria-label="Shop Gold Vault">
      <span className="vault-icon" aria-hidden="true">🪙</span>
      <div>
        <p className="vault-label">Shop Gold Vault</p>
        <p className="vault-gold" aria-live="polite">{cash ? `$${fmt(shown)}` : "…"}<span className="sr-only"> checking balance {cash ? fmt(target) : ""}</span></p>
        {cash && cash.pending_requests_total > 0 && (
          <p className="vault-pending">${fmt(cash.pending_requests_total)} promised to unsealed scrolls</p>
        )}
      </div>
    </div>
  );
}
