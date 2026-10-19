import { useEffect, useState } from "react";
import { api, formatDate, type Conversation, type Message } from "../api";
import type { PageProps } from "../App";

/** The assistant writes **bold**; show it as bold, everything else as plain text. */
function Rich({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part)}</>;
}

export default function Conversations({ site, role }: PageProps) {
  const [list, setList] = useState<Conversation[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    api.conversations(site.id).then((l) => {
      setList(l);
      setSelected(l[0]?.id ?? null);
    });
  }, [site.id]);

  useEffect(() => {
    if (selected) api.conversation(selected).then(setMessages);
  }, [selected]);

  if (!list) return <p className="muted">Chargement…</p>;
  if (!list.length) return <div className="card"><p className="muted">Aucune conversation pour l'instant.</p></div>;

  return (
    <div className="split">
      <section className="card list-pane">
        <h2>Conversations ({list.length})</h2>
        {role !== "admin" && <p className="hint">Démo : e-mails et numéros des visiteurs masqués.</p>}
        <ul className="conv-list">
          {list.map((c) => (
            <li key={c.id}>
              <button className={selected === c.id ? "active" : ""} onClick={() => setSelected(c.id)}>
                <span className="conv-q">{c.first_question || "…"}</span>
                <span className="hint">
                  {formatDate(c.updated_at)} · {c.questions} question{c.questions > 1 ? "s" : ""}
                  {c.handoff ? <span className="tag warn">transfert</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="card thread">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="bubble-text"><Rich text={m.content} /></div>
            {m.sources.length > 0 && (
              <div className="hint">Sources : {m.sources.map((s) => s.title).join(" · ")}</div>
            )}
            {m.handoff ? <div className="tag warn">Proposé de transmettre à l'équipe</div> : null}
          </div>
        ))}
      </section>
    </div>
  );
}
