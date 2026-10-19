import { useCallback, useEffect, useState } from "react";
import { api, ApiError, session, type Role, type Site } from "./api";
import Overview from "./pages/Overview";
import Knowledge from "./pages/Knowledge";
import SearchTest from "./pages/SearchTest";
import Conversations from "./pages/Conversations";
import Leads from "./pages/Leads";
import Install from "./pages/Install";

const TABS = [
  { id: "overview", label: "Vue d'ensemble" },
  { id: "knowledge", label: "Connaissances" },
  { id: "search", label: "Tester la recherche" },
  { id: "conversations", label: "Conversations" },
  { id: "leads", label: "Contacts" },
  { id: "install", label: "Installation & réglages" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export interface PageProps {
  site: Site;
  role: Role;
  onSiteChange: (site: Site) => void;
}

function tabFromHash(): Tab {
  const id = window.location.hash.slice(2);
  return (TABS.find((t) => t.id === id)?.id ?? "overview") as Tab;
}

export default function App() {
  const [auth, setAuth] = useState(session.get());
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    session.set(null);
    setAuth(null);
  }, []);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!auth) return;
    api.sites()
      .then((list) => {
        setSites(list);
        setSiteId((cur) => cur ?? list[0]?.id ?? null);
      })
      .catch((e) => (e instanceof ApiError && e.status === 401 ? logout() : setError(e.message)));
  }, [auth, logout]);

  if (!auth) return <Login onLogin={(a) => { session.set(a); setAuth(a); }} />;

  const site = sites.find((s) => s.id === siteId);
  const onSiteChange = (updated: Site) => setSites((list) => list.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)));

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 32 32" width="24" height="24"><rect width="32" height="32" rx="8" fill="var(--accent)" /><path d="M9 21a7 7 0 1 1 3 2l-4 1z" fill="white" /></svg>
          </span>
          Site Assistant
        </div>
        {sites.length > 0 && (
          <select value={siteId ?? ""} onChange={(e) => setSiteId(e.target.value)} aria-label="Site">
            {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        )}
        <div className="spacer" />
        {auth.role === "viewer" && <span className="badge">Démo · lecture seule</span>}
        <button className="btn ghost small" onClick={logout}>Se déconnecter</button>
      </header>
      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <a key={t.id} href={`#/${t.id}`} className={tab === t.id ? "active" : ""}>{t.label}</a>
        ))}
      </nav>
      <main className="content">
        {error && <div className="alert error">{error}</div>}
        {site ? (
          <>
            {tab === "overview" && <Overview site={site} role={auth.role} onSiteChange={onSiteChange} />}
            {tab === "knowledge" && <Knowledge site={site} role={auth.role} onSiteChange={onSiteChange} />}
            {tab === "search" && <SearchTest site={site} role={auth.role} onSiteChange={onSiteChange} />}
            {tab === "conversations" && <Conversations site={site} role={auth.role} onSiteChange={onSiteChange} />}
            {tab === "leads" && <Leads site={site} role={auth.role} onSiteChange={onSiteChange} />}
            {tab === "install" && <Install site={site} role={auth.role} onSiteChange={onSiteChange} />}
          </>
        ) : (
          !error && <p className="muted">Chargement…</p>
        )}
      </main>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (a: { token: string; role: Role }) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await api.login(password));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <h1>Site Assistant</h1>
        <p className="muted">Tableau de bord de l'assistant IA.</p>
        <label className="field">
          <span>Mot de passe</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus autoComplete="current-password" />
        </label>
        {error && <div className="alert error">{error}</div>}
        <button className="btn primary" disabled={busy || !password}>{busy ? "Connexion…" : "Se connecter"}</button>
        <p className="hint">Démo publique : utilisez le mot de passe <strong>demo</strong> pour visiter en lecture seule. Les données des visiteurs y sont anonymisées.</p>
      </form>
    </div>
  );
}
