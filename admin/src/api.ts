export type Role = "admin" | "viewer";

export interface Site {
  id: string;
  name: string;
  language: string;
  color: string;
  welcome: string;
  suggestions: string[];
  instructions: string;
  allowed_origins: string;
  documents?: number;
  chunks?: number;
  conversations?: number;
  leads?: number;
}

export interface Stats {
  conversations: number;
  questions: number;
  handoffs: number;
  leads: number;
  documents: number;
  chunks: number;
  daily: { day: string; questions: number }[];
  usage_today: number;
  daily_limit: number;
}

export interface Doc {
  id: number;
  title: string;
  source: string;
  kind: "page" | "pdf" | "text";
  chars: number;
  chunks: number;
  created_at: string;
}

export interface ChunkRow {
  id: number;
  heading: string;
  url: string | null;
  text: string;
}

export interface SearchHit {
  heading: string;
  url: string | null;
  text: string;
  score: number;
  similarity: number;
  keyword_score: number;
}

export interface Conversation {
  id: string;
  page_url: string | null;
  started_at: string;
  updated_at: string;
  questions: number;
  handoff: number | null;
  first_question: string | null;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources: { title: string; url: string }[];
  handoff: number;
  created_at: string;
}

export interface Lead {
  id: number;
  name: string;
  email: string;
  message: string | null;
  page_url: string | null;
  conversation_id: string | null;
  created_at: string;
}

/** API server. Empty = same origin (served by the backend); set VITE_API_URL when the
 * dashboard is hosted elsewhere, e.g. on GitHub Pages. */
export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

const TOKEN_KEY = "site-assistant-admin";

export const session = {
  get(): { token: string; role: Role } | null {
    try {
      return JSON.parse(localStorage.getItem(TOKEN_KEY) || "null");
    } catch {
      return null;
    }
  },
  set(value: { token: string; role: Role } | null) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, JSON.stringify(value));
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* private mode: the session lasts for this page only */
    }
  },
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = session.get()?.token;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(API_BASE + path, { ...init, headers });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) message = typeof body.detail === "string" ? body.detail : "Données invalides";
    } catch {
      /* keep the status text */
    }
    throw new ApiError(message, res.status);
  }
  return res.json();
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  login: (password: string) => request<{ token: string; role: Role }>("/api/admin/login", post({ password })),
  me: () => request<{ role: Role; model: string; embedding_model: string }>("/api/admin/me"),
  sites: () => request<Site[]>("/api/admin/sites"),
  createSite: (id: string, name: string) => request<Site>("/api/admin/sites", post({ id, name })),
  updateSite: (site: Site) => request<Site>(`/api/admin/sites/${site.id}`, { method: "PUT", body: JSON.stringify(site) }),
  stats: (siteId: string) => request<Stats>(`/api/admin/sites/${siteId}/stats`),
  documents: (siteId: string) => request<Doc[]>(`/api/admin/sites/${siteId}/documents`),
  chunks: (docId: number) => request<ChunkRow[]>(`/api/admin/documents/${docId}/chunks`),
  upload: (siteId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ title: string; chunks: number }>(`/api/admin/sites/${siteId}/documents/upload`, { method: "POST", body: form });
  },
  importUrl: (siteId: string, url: string, followLinks: boolean) =>
    request<{ imported: { title: string; chunks: number }[]; errors: { url: string; error: string }[] }>(
      `/api/admin/sites/${siteId}/documents/url`, post({ url, follow_links: followLinks })),
  deleteDocument: (docId: number) => request<{ ok: boolean }>(`/api/admin/documents/${docId}`, { method: "DELETE" }),
  search: (siteId: string, query: string) => request<SearchHit[]>(`/api/admin/sites/${siteId}/search`, post({ query })),
  conversations: (siteId: string) => request<Conversation[]>(`/api/admin/sites/${siteId}/conversations`),
  conversation: (id: string) => request<Message[]>(`/api/admin/conversations/${id}`),
  leads: (siteId: string) => request<Lead[]>(`/api/admin/sites/${siteId}/leads`),
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
