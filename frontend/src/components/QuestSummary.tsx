import { who, type Summary } from "../party";

export default function QuestSummary({ items, title, sealsPending }: { items: Summary[]; title: string; sealsPending: number }) {
  return (
    <section aria-labelledby="sum-h" className="victory">
      <div className="victory-banner">
        <h2 id="sum-h">🏆 Quest Complete — {title}</h2>
        <p>{sealsPending > 0
          ? `The party has done all it may. ${sealsPending} payment${sealsPending > 1 ? "s" : ""} still await the Guild Master's Seal.`
          : "The party has done all it may. No gold awaits your Seal."}</p>
      </div>
      <div className="sum-grid">
        {items.map((s) => {
          const c = who(s.agent);
          return (
            <article key={s.agent} className="sum-card">
              <h3><span aria-hidden="true">{c.icon}</span> {c.name} <small>{c.role}</small></h3>
              {s.text && <p className="sum-text">{s.text}</p>}
              {s.findings.length > 0 && <><h4>{s.agent === "boss" ? "Orders given" : "Learned"}</h4><ul>{s.findings.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
              {s.actions.length > 0 && <><h4>{s.agent === "boss" ? "Scrolls saved" : "Did"}</h4><ul>{s.actions.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
              {s.approvals.length > 0 && <><h4 className="seal-h">Awaiting the Seal</h4><ul>{s.approvals.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
