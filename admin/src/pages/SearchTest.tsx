import { useState } from "react";
import { api, type SearchHit } from "../api";
import type { PageProps } from "../App";

const EXAMPLES = ["Vous envoyez à Bruxelles ?", "Do you ship to Switzerland?", "bougie pour dormir", "ma commande est arrivée cassée"];

export default function SearchTest({ site }: PageProps) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async (q: string) => {
    if (!q.trim()) return;
    setQuery(q);
    setBusy(true);
    setError(null);
    try {
      setHits(await api.search(site.id, q));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <h2>Tester la recherche</h2>
        <p className="muted">Voyez exactement quels passages l'assistant lit avant de répondre. Utile pour vérifier qu'une information est bien trouvée, et pour comprendre une mauvaise réponse.</p>
        <form className="row gap" onSubmit={(e) => { e.preventDefault(); search(query); }}>
          <input className="grow" placeholder="Une question de visiteur…" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="btn primary" disabled={busy || !query.trim()}>{busy ? "Recherche…" : "Chercher"}</button>
        </form>
        <div className="row gap wrap examples">
          {EXAMPLES.map((q) => <button key={q} className="chip-btn" onClick={() => search(q)}>{q}</button>)}
        </div>
        {error && <div className="alert error">{error}</div>}
      </section>

      {hits && (
        <section className="card">
          <h2>Passages trouvés</h2>
          <p className="hint">Score = 65 % similarité sémantique + 35 % mots-clés (BM25, relatif au meilleur résultat).</p>
          {hits.map((h, i) => (
            <div key={i} className="hit">
              <div className="hit-head">
                <span className="rank">{i + 1}</span>
                <strong>{h.heading}</strong>
                {h.url && <span className="hint">{h.url}</span>}
                <span className="spacer" />
                <span className="score" title="Score final">{h.score.toFixed(2)}</span>
              </div>
              <div className="meter" aria-hidden><div style={{ width: `${Math.max(0, Math.min(1, h.score)) * 100}%` }} /></div>
              <div className="hint">sémantique {h.similarity.toFixed(2)} · mots-clés {h.keyword_score.toFixed(1)}</div>
              <p>{h.text.split("\n").slice(1).join(" ")}</p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
