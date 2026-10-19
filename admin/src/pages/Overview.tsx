import { useEffect, useState } from "react";
import { api, type Stats } from "../api";
import type { PageProps } from "../App";

export default function Overview({ site }: PageProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [models, setModels] = useState<{ model: string; embedding_model: string } | null>(null);

  useEffect(() => {
    api.stats(site.id).then(setStats);
    api.me().then(setModels);
  }, [site.id]);

  if (!stats) return <p className="muted">Chargement…</p>;
  const max = Math.max(1, ...stats.daily.map((d) => d.questions));

  return (
    <div className="stack">
      <div className="stat-grid">
        <Stat label="Conversations" value={stats.conversations} />
        <Stat label="Questions posées" value={stats.questions} />
        <Stat label="Transferts à l'équipe" value={stats.handoffs} />
        <Stat label="Contacts récoltés" value={stats.leads} />
        <Stat label="Documents" value={stats.documents} hint={`${stats.chunks} passages indexés`} />
        <Stat label="Messages aujourd'hui" value={stats.usage_today} hint={`limite ${stats.daily_limit} / jour`} />
      </div>

      <section className="card">
        <h2>Questions par jour (14 derniers jours)</h2>
        {stats.daily.length ? (
          <div className="bars" role="img" aria-label="Questions par jour">
            {stats.daily.map((d) => (
              <div key={d.day} className="bar-col" title={`${d.day} : ${d.questions} questions`}>
                <span className="bar-value">{d.questions}</span>
                <div className="bar" style={{ height: `${(d.questions / max) * 100}%` }} />
                <span className="bar-label">{d.day.slice(8)}/{d.day.slice(5, 7)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">Pas encore de questions. Essayez l'assistant sur le site de démonstration.</p>
        )}
      </section>

      <section className="card">
        <h2>Comment ça marche</h2>
        <ol className="pipeline">
          <li>
            <strong>Lecture du site</strong>
            <span>Les pages, PDF et documents du client sont découpés en passages courts (une fiche produit, une question de FAQ, une section).</span>
          </li>
          <li>
            <strong>Indexation multilingue</strong>
            <span>Chaque passage est transformé en vecteur par un modèle d'embeddings exécuté sur le serveur{models ? ` (${models.embedding_model.split("/").pop()})` : ""}. Aucune donnée n'est envoyée pour cette étape.</span>
          </li>
          <li>
            <strong>Recherche hybride</strong>
            <span>À chaque question, l'assistant combine recherche sémantique (sens, paraphrases, autres langues) et recherche par mots-clés (noms de produits, prix).</span>
          </li>
          <li>
            <strong>Réponse sourcée</strong>
            <span>Le modèle de langage{models ? ` (${models.model})` : ""} rédige une réponse courte uniquement à partir des passages trouvés, avec les liens vers les pages. S'il ne sait pas, il propose de transmettre à l'équipe.</span>
          </li>
        </ol>
      </section>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="stat card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
