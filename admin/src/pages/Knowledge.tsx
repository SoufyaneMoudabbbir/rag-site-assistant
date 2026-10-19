import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api, formatDate, type ChunkRow, type Doc } from "../api";
import type { PageProps } from "../App";

const KIND_LABEL = { page: "Page web", pdf: "PDF", text: "Texte" };

export default function Knowledge({ site, role }: PageProps) {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [chunks, setChunks] = useState<ChunkRow[]>([]);
  const [url, setUrl] = useState("");
  const [follow, setFollow] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const readOnly = role !== "admin";

  const load = useCallback(() => api.documents(site.id).then(setDocs), [site.id]);
  useEffect(() => { load(); }, [load]);

  const toggle = async (id: number) => {
    if (open === id) return setOpen(null);
    setOpen(id);
    setChunks(await api.chunks(id));
  };

  const run = async (label: string, fn: () => Promise<string>) => {
    setBusy(label);
    setMessage(null);
    try {
      setMessage({ text: await fn() });
      await load();
    } catch (e) {
      setMessage({ text: (e as Error).message, error: true });
    } finally {
      setBusy(null);
    }
  };

  const upload = (file: File) =>
    run("upload", async () => {
      const r = await api.upload(site.id, file);
      return `« ${r.title} » importé : ${r.chunks} passages indexés.`;
    });

  const importUrl = (e: React.FormEvent) => {
    e.preventDefault();
    run("url", async () => {
      const r = await api.importUrl(site.id, url.trim(), follow);
      setUrl("");
      const total = r.imported.reduce((n, d) => n + d.chunks, 0);
      return `${r.imported.length} page(s) importée(s), ${total} passages.` + (r.errors.length ? ` ${r.errors.length} erreur(s).` : "");
    });
  };

  const remove = (doc: Doc) => {
    if (!window.confirm(`Supprimer « ${doc.title} » de la base de connaissances ?`)) return;
    run("delete", async () => {
      await api.deleteDocument(doc.id);
      return "Document supprimé.";
    });
  };

  return (
    <div className="stack">
      <section className="card">
        <h2>Ajouter du contenu</h2>
        {readOnly && <div className="alert">Compte de démonstration : l'import est désactivé, mais vous pouvez parcourir les documents et leurs passages ci-dessous.</div>}
        <div className="import-grid">
          <form onSubmit={importUrl} className="stack-sm">
            <label className="field">
              <span>Importer une page web</span>
              <input type="url" placeholder="https://www.client.fr/livraison" value={url} onChange={(e) => setUrl(e.target.value)} disabled={readOnly} />
            </label>
            <label className="check">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} disabled={readOnly} />
              Importer aussi les pages liées (30 max)
            </label>
            <button className="btn primary" disabled={readOnly || !url.trim() || busy !== null}>{busy === "url" ? "Import…" : "Importer"}</button>
          </form>
          <div className="stack-sm">
            <span className="field-label">Importer un fichier</span>
            <p className="hint">PDF, TXT, Markdown ou HTML, 5 Mo max : catalogue, CGV, fiches produits, FAQ…</p>
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.html,.htm" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <button className="btn" disabled={readOnly || busy !== null} onClick={() => fileRef.current?.click()}>
              {busy === "upload" ? "Import…" : "Choisir un fichier"}
            </button>
          </div>
        </div>
        {message && <div className={"alert" + (message.error ? " error" : " ok")}>{message.text}</div>}
      </section>

      <section className="card">
        <h2>Base de connaissances</h2>
        {!docs ? (
          <p className="muted">Chargement…</p>
        ) : !docs.length ? (
          <p className="muted">Aucun document. Importez les pages du site du client pour commencer.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Document</th><th>Type</th><th>Passages</th><th>Ajouté</th><th /></tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <Fragment key={d.id}>
                    <tr className="clickable" onClick={() => toggle(d.id)}>
                      <td><strong>{d.title}</strong><div className="hint">{d.source}</div></td>
                      <td>{KIND_LABEL[d.kind]}</td>
                      <td>{d.chunks}</td>
                      <td>{formatDate(d.created_at)}</td>
                      <td className="actions">
                        <button className="btn ghost small" onClick={(e) => { e.stopPropagation(); toggle(d.id); }}>{open === d.id ? "Masquer" : "Voir"}</button>
                        {!readOnly && <button className="btn ghost small danger" onClick={(e) => { e.stopPropagation(); remove(d); }}>Supprimer</button>}
                      </td>
                    </tr>
                    {open === d.id && (
                      <tr className="chunks-row">
                        <td colSpan={5}>
                          {chunks.map((c, i) => (
                            <div key={c.id} className="chunk">
                              <span className="chunk-n">#{i + 1}</span> <strong>{c.heading}</strong>
                              {c.url && <span className="hint"> · {c.url}</span>}
                              <p>{c.text.split("\n").slice(1).join(" ")}</p>
                            </div>
                          ))}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
