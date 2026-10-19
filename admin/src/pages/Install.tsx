import { useEffect, useState } from "react";
import { API_BASE, api, type Site } from "../api";
import type { PageProps } from "../App";

export default function Install({ site, role, onSiteChange }: PageProps) {
  const [form, setForm] = useState<Site>(site);
  const [suggestions, setSuggestions] = useState(site.suggestions.join("\n"));
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const readOnly = role !== "admin";

  useEffect(() => {
    setForm(site);
    setSuggestions(site.suggestions.join("\n"));
  }, [site]);

  const snippet = `<script src="${API_BASE || window.location.origin}/widget.js" data-site="${site.id}" defer></script>`;
  const set = <K extends keyof Site>(k: K, v: Site[K]) => setForm((f) => ({ ...f, [k]: v }));

  const copy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus(null);
    try {
      const updated = await api.updateSite({ ...form, suggestions: suggestions.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 6) });
      onSiteChange(updated);
      setStatus({ text: "Réglages enregistrés. Rechargez le site pour voir les changements." });
    } catch (err) {
      setStatus({ text: (err as Error).message, error: true });
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <h2>Installer l'assistant</h2>
        <p className="muted">Une seule ligne à ajouter avant <code>&lt;/body&gt;</code>, sur n'importe quel site :</p>
        <div className="snippet">
          <code>{snippet}</code>
          <button className="btn small" onClick={copy}>{copied ? "Copié" : "Copier"}</button>
        </div>
        <div className="install-grid">
          <div><strong>WordPress</strong><p className="hint">Extension « WPCode » (ou le pied de page du thème) → coller la ligne dans « Footer ».</p></div>
          <div><strong>Shopify</strong><p className="hint">Boutique en ligne → Thèmes → Modifier le code → <code>theme.liquid</code>, avant <code>&lt;/body&gt;</code>.</p></div>
          <div><strong>Webflow, Wix, autres</strong><p className="hint">Réglages du site → Code personnalisé → pied de page.</p></div>
        </div>
        <p className="hint">Options : <code>data-teaser="true"</code> affiche une bulle d'invitation, <code>data-theme="auto"</code> suit le mode sombre du visiteur.</p>
      </section>

      <form className="card" onSubmit={save}>
        <div className="card-head">
          <h2>Réglages de l'assistant</h2>
          {!readOnly && <button className="btn primary">Enregistrer</button>}
        </div>
        {readOnly && <div className="alert">Compte de démonstration : les réglages sont visibles mais ne peuvent pas être modifiés.</div>}
        <fieldset disabled={readOnly} className="settings-grid">
          <label className="field">
            <span>Nom affiché</span>
            <input value={form.name} onChange={(e) => set("name", e.target.value)} />
          </label>
          <label className="field">
            <span>Couleur</span>
            <div className="row gap">
              <input type="color" value={form.color} onChange={(e) => set("color", e.target.value)} className="color" />
              <input value={form.color} onChange={(e) => set("color", e.target.value)} />
            </div>
          </label>
          <label className="field">
            <span>Langue de l'interface</span>
            <select value={form.language} onChange={(e) => set("language", e.target.value)}>
              <option value="fr">Français</option>
              <option value="en">English</option>
            </select>
            <small className="hint">L'assistant répond toujours dans la langue du visiteur.</small>
          </label>
          <label className="field">
            <span>Sites autorisés</span>
            <input value={form.allowed_origins} onChange={(e) => set("allowed_origins", e.target.value)} placeholder="https://www.client.fr" />
            <small className="hint">Séparés par des virgules. « * » = partout.</small>
          </label>
          <label className="field span-2">
            <span>Message d'accueil</span>
            <textarea rows={2} value={form.welcome} onChange={(e) => set("welcome", e.target.value)} />
          </label>
          <label className="field">
            <span>Questions suggérées (une par ligne)</span>
            <textarea rows={4} value={suggestions} onChange={(e) => setSuggestions(e.target.value)} />
          </label>
          <label className="field">
            <span>Consignes de ton (optionnel)</span>
            <textarea rows={4} value={form.instructions} onChange={(e) => set("instructions", e.target.value)} placeholder="Ex. : vouvoyer, ton chaleureux, mettre en avant les ateliers…" />
          </label>
        </fieldset>
        {status && <div className={"alert" + (status.error ? " error" : " ok")}>{status.text}</div>}
      </form>
    </div>
  );
}
