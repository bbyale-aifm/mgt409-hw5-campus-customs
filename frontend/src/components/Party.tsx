import { BOSS, NPCS, spell, type CharState, type Character } from "../party";

function Card({ c, st, big }: { c: Character; st: CharState; big?: boolean }) {
  const cls = `char ${big ? "char-boss" : ""} ${st.active ? "active" : ""} ${st.done ? "done" : ""}`;
  return (
    <article className={cls} aria-label={`${c.name}, ${c.role}${st.active ? ", acting now" : ""}`}>
      <div className="char-icon" aria-hidden="true">{c.icon}</div>
      <h3>{c.name}</h3>
      <p className="char-role">{c.role}</p>
      <p className="char-blurb">{c.blurb}</p>
      <div className="char-status" aria-live="polite">
        {st.active && st.lastTool ? (
          <span className="glow-chip"><span className="pulse" /> {spell(st.lastTool)}</span>
        ) : st.active ? (
          <span className="glow-chip"><span className="pulse" /> waking up…</span>
        ) : st.done ? (
          <span className="done-chip">✔ Task done · {st.actions} action{st.actions === 1 ? "" : "s"}</span>
        ) : (
          <span className="idle-chip">Waiting in the tavern</span>
        )}
      </div>
    </article>
  );
}

export default function Party({ state }: { state: Record<string, CharState> }) {
  return (
    <section aria-labelledby="party-h" className="party">
      <h2 id="party-h">The Party</h2>
      <div className="party-grid">
        <Card c={BOSS} st={state.boss} big />
        <div className="npcs">{NPCS.map((c) => <Card key={c.id} c={c} st={state[c.id]} />)}</div>
      </div>
    </section>
  );
}
