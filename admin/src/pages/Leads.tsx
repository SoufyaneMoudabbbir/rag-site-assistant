import { useEffect, useState } from "react";
import { api, formatDate, type Lead } from "../api";
import type { PageProps } from "../App";

function toCsv(leads: Lead[]): string {
  const cell = (v: string | null) => `"${(v ?? "").replace(/"/g, '""')}"`;
  const rows = leads.map((l) => [l.created_at, l.name, l.email, l.message, l.page_url].map(cell).join(","));
  return ["date,nom,email,message,page", ...rows].join("\n");
}

export default function Leads({ site, role }: PageProps) {
  const [leads, setLeads] = useState<Lead[] | null>(null);

  useEffect(() => {
    api.leads(site.id).then(setLeads);
  }, [site.id]);

  const download = () => {
    if (!leads) return;
    const blob = new Blob(["﻿" + toCsv(leads)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `contacts-${site.id}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (!leads) return <p className="muted">Chargement…</p>;

  return (
    <section className="card">
      <div className="card-head">
        <h2>Contacts ({leads.length})</h2>
        {role === "admin" && leads.length > 0 && <button className="btn" onClick={download}>Exporter en CSV</button>}
      </div>
      <p className="muted">Visiteurs qui ont demandé à être recontactés depuis l'assistant (devis, commande personnalisée, question sans réponse).</p>
      {role !== "admin" && <p className="hint">Démo : noms, e-mails et numéros masqués.</p>}
      {!leads.length ? (
        <p className="muted">Aucun contact pour l'instant.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Nom</th><th>E-mail</th><th>Message</th><th>Page</th></tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id}>
                  <td className="nowrap">{formatDate(l.created_at)}</td>
                  <td>{l.name || "—"}</td>
                  <td>{role === "admin" ? <a href={`mailto:${l.email}`}>{l.email}</a> : l.email}</td>
                  <td className="msg-cell">{l.message || "—"}</td>
                  <td className="hint">{l.page_url ? new URL(l.page_url).pathname : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
