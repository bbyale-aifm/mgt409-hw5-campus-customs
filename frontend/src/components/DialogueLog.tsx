import { useEffect, useRef } from "react";
import { who, type LogLine } from "../party";

export default function DialogueLog({ lines, running }: { lines: LogLine[]; running: boolean }) {
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [lines.length]);
  return (
    <section aria-labelledby="log-h" className="log">
      <h2 id="log-h">Party Dialogue {running && <span className="live">● LIVE</span>}</h2>
      <ol className="log-list" role="log" aria-live="polite">
        {lines.length === 0 && <li className="muted">Pick a quest and press “Begin Quest”. The party’s words and spells will appear here.</li>}
        {lines.map((l) => {
          const c = who(l.agent);
          return (
            <li key={l.seq} className={`line line-${l.kind} who-${l.agent}`}>
              <span className="line-icon" aria-hidden="true">{c.icon}</span>
              <div>
                <span className="line-name">
                  {c.name}
                  {l.to && <> <span className="arrow">➜</span> {who(l.to).name}</>}
                </span>
                {l.kind === "action" ? (
                  <p className="line-text"><span className="spell">⚡ {l.tool}</span> {l.text}</p>
                ) : l.kind === "result" ? (
                  <p className="line-text result"><span className="spell dim">↳ {l.tool}</span> {l.text}</p>
                ) : (
                  <p className="line-text">{l.kind === "report" ? "“" : ""}{l.text}{l.kind === "report" ? "”" : ""}</p>
                )}
              </div>
            </li>
          );
        })}
        <li ref={end} aria-hidden="true" />
      </ol>
    </section>
  );
}
