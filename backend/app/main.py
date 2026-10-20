"""FastAPI app: public chat API for the widget, admin API, and static files."""

import asyncio
import json
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import config, db, embeddings, ingest, knowledge, llm, products, retrieval, seed
from app.security import check_rate, login, mask_email, redact, require_admin, require_viewer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    await run_in_threadpool(embeddings.model)  # load the model before the first visitor
    await run_in_threadpool(seed.seed)
    yield


app = FastAPI(title="Site Assistant", lifespan=lifespan)
# The widget runs on client websites, so the public API is called cross-origin.
# Admin routes use bearer tokens (no cookies), so a wildcard origin is safe here;
# each site can still restrict where its widget may be used (allowed_origins).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_site_or_404(site_id: str) -> dict:
    with db.connect() as conn:
        site = db.get_site(conn, site_id)
    if not site:
        raise HTTPException(404, "Unknown site")
    return site


def check_origin(site: dict, request: Request) -> None:
    allowed = [o.strip().rstrip("/") for o in site["allowed_origins"].split(",") if o.strip()]
    origin = (request.headers.get("origin") or "").rstrip("/")
    if "*" in allowed or not origin or origin in allowed:
        return
    raise HTTPException(403, "This assistant is not enabled on this website")


# ================================================================ public API (widget)


@app.get("/api/sites/{site_id}/config")
def widget_config(site_id: str, request: Request):
    site = get_site_or_404(site_id)
    check_origin(site, request)
    return {k: site[k] for k in ("id", "name", "language", "color", "welcome", "suggestions")}


class ChatRequest(BaseModel):
    site_id: str
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    page_url: str | None = None


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def load_history(conn, conversation_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conversation_id, config.MAX_HISTORY_TURNS * 2),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def pick_sources(hits: list[retrieval.Hit]) -> list[dict]:
    """The pages worth linking under an answer: strong matches only, one per page section."""
    if not hits:
        return []
    # Strong matches only, and close to the best one: weaker hits were read but not used.
    cutoff = max(0.5, hits[0].score - 0.1)
    sources, seen = [], set()
    for h in hits:
        if h.score < cutoff or not h.url or h.url in seen:
            continue
        seen.add(h.url)
        sources.append({"title": h.heading, "url": h.url})
        if len(sources) == 2:
            break
    return sources


async def find_passages(site: dict, query: str) -> list[retrieval.Hit]:
    """Hybrid search. A question in another language than the site's is also searched
    translated: across languages, generic words ("candle") outweigh the ones that
    matter ("vanilla")."""
    def search(q: str):
        return run_in_threadpool(retrieval.search, site["id"], q, config.TOP_K)

    if retrieval.is_in_language(query, site["language"]):
        return await search(query)
    hits, translated = await asyncio.gather(search(query), translate(query, site["language"]))
    if not translated:
        return hits
    return retrieval.merge(hits, await search(translated), k=config.TOP_K)


async def translate(query: str, language: str) -> str | None:
    try:
        return await llm.translate_query(query, language)
    except Exception as e:  # the original question alone still gives an answer
        print(f"Query translation error: {type(e).__name__}: {e}")
        return None


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    site = get_site_or_404(req.site_id)
    check_origin(site, request)
    check_rate(request)
    question = req.message.strip()[: config.MAX_MESSAGE_CHARS]

    with db.connect() as conn:
        if db.count_usage(conn) >= config.DAILY_MESSAGE_LIMIT:
            raise HTTPException(429, "L'assistant de démonstration a atteint sa limite du jour. Revenez demain !")
        conv_id = req.conversation_id
        known = conv_id and conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND site_id = ?", (conv_id, site["id"])
        ).fetchone()
        if not known:
            conv_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO conversations (id, site_id, page_url, started_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conv_id, site["id"], req.page_url, db.now(), db.now()),
            )
        history = load_history(conn, conv_id)
        db.add_usage(conn)

    hits = await find_passages(site, question)
    sources = pick_sources(hits)
    # A short follow-up ("et en Suisse ?") may only make sense with the previous question:
    # also search both together. Sources come from the question alone when it found a
    # strong match itself ("Vous livrez en Belgique ?" after a question about flowers).
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    if last_user and len(question.split()) < 6:
        together = await run_in_threadpool(retrieval.search, site["id"], f"{last_user} {question}", config.TOP_K)
        if not sources:
            sources = pick_sources(together)
        hits = retrieval.merge(hits, together, k=config.TOP_K)
    messages = llm.build_messages(site, hits, history, question)

    async def events():
        yield sse("start", {"conversation_id": conv_id, "sources": sources})
        marker, answer = llm.MarkerFilter(), []
        try:
            async for token in llm.stream_answer(messages):
                text = marker.feed(token)
                if text:
                    answer.append(text)
                    yield sse("token", {"t": text})
            tail = marker.flush()
            if tail:
                answer.append(tail)
                yield sse("token", {"t": tail})
        except Exception as e:  # network/API problem: tell the visitor, keep the server up
            yield sse("error", {"message": "L'assistant est momentanément indisponible. Réessayez dans un instant."})
            print(f"LLM error: {type(e).__name__}: {e}")
            return
        text = "".join(answer).strip()
        cards = await run_in_threadpool(products.mentioned_products, site["id"], text)
        if cards:
            yield sse("products", {"products": cards})
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (conv_id, question, db.now()),
            )
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, sources, handoff, created_at) "
                "VALUES (?, 'assistant', ?, ?, ?, ?)",
                (conv_id, text, json.dumps(sources, ensure_ascii=False), int(marker.found), db.now()),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (db.now(), conv_id))
        yield sse("done", {"handoff": marker.found})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class LeadRequest(BaseModel):
    site_id: str
    email: str
    name: str | None = None
    message: str | None = None
    conversation_id: str | None = None
    page_url: str | None = None


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/leads")
def create_lead(req: LeadRequest, request: Request):
    site = get_site_or_404(req.site_id)
    check_origin(site, request)
    check_rate(request, "lead")
    if not EMAIL_RE.match(req.email.strip()):
        raise HTTPException(400, "Adresse e-mail invalide")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO leads (site_id, conversation_id, name, email, message, page_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (site["id"], req.conversation_id, (req.name or "")[:120], req.email.strip()[:200],
             (req.message or "")[:2000], req.page_url, db.now()),
        )
    return {"ok": True}


# ================================================================ admin API


class LoginRequest(BaseModel):
    password: str


@app.post("/api/admin/login")
def admin_login(req: LoginRequest, request: Request):
    check_rate(request, "login")
    result = login(req.password)
    if not result:
        raise HTTPException(401, "Mot de passe incorrect")
    role, token = result
    return {"token": token, "role": role}


@app.get("/api/admin/me")
def admin_me(role: str = Depends(require_viewer)):
    return {"role": role, "model": config.LLM_MODEL, "embedding_model": config.EMBED_MODEL}


@app.get("/api/admin/sites")
def admin_sites(_: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = conn.execute("""
            SELECT s.*,
              (SELECT COUNT(*) FROM documents d WHERE d.site_id = s.id) documents,
              (SELECT COUNT(*) FROM chunks c WHERE c.site_id = s.id) chunks,
              (SELECT COUNT(*) FROM conversations v WHERE v.site_id = s.id) conversations,
              (SELECT COUNT(*) FROM leads l WHERE l.site_id = s.id) leads
            FROM sites s ORDER BY s.created_at""").fetchall()
    return [db.site_to_dict(r) for r in rows]


class SiteCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,40}$")
    name: str = Field(min_length=1, max_length=80)


@app.post("/api/admin/sites")
def admin_create_site(req: SiteCreate, _: str = Depends(require_admin)):
    with db.connect() as conn:
        if db.get_site(conn, req.id):
            raise HTTPException(409, "A site with this id already exists")
        conn.execute(
            "INSERT INTO sites (id, name, welcome, suggestions, created_at) VALUES (?, ?, ?, '[]', ?)",
            (req.id, req.name, f"Bonjour ! Je suis l'assistant de {req.name}. Comment puis-je vous aider ?", db.now()),
        )
    return get_site_or_404(req.id)


class SiteUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    language: str = "fr"
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    welcome: str = Field(max_length=400)
    suggestions: list[str] = Field(max_length=6)
    instructions: str = Field(default="", max_length=1500)
    allowed_origins: str = "*"


@app.get("/api/admin/sites/{site_id}")
def admin_site(site_id: str, _: str = Depends(require_viewer)):
    return get_site_or_404(site_id)


@app.put("/api/admin/sites/{site_id}")
def admin_update_site(site_id: str, req: SiteUpdate, _: str = Depends(require_admin)):
    get_site_or_404(site_id)
    with db.connect() as conn:
        conn.execute(
            "UPDATE sites SET name=?, language=?, color=?, welcome=?, suggestions=?, instructions=?, allowed_origins=? WHERE id=?",
            (req.name, req.language, req.color, req.welcome,
             json.dumps([s for s in req.suggestions if s.strip()], ensure_ascii=False),
             req.instructions, req.allowed_origins or "*", site_id),
        )
    return get_site_or_404(site_id)


@app.get("/api/admin/sites/{site_id}/stats")
def admin_stats(site_id: str, _: str = Depends(require_viewer)):
    get_site_or_404(site_id)
    with db.connect() as conn:
        one = lambda sql: conn.execute(sql, (site_id,)).fetchone()[0]  # noqa: E731
        daily = conn.execute("""
            SELECT substr(m.created_at, 1, 10) day, COUNT(*) questions
            FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE c.site_id = ? AND m.role = 'user' AND m.created_at >= date('now', '-13 days')
            GROUP BY day ORDER BY day""", (site_id,)).fetchall()
        return {
            "conversations": one("SELECT COUNT(*) FROM conversations WHERE site_id = ?"),
            "questions": one("SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.site_id = ? AND m.role = 'user'"),
            "handoffs": one("SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.site_id = ? AND m.handoff = 1"),
            "leads": one("SELECT COUNT(*) FROM leads WHERE site_id = ?"),
            "documents": one("SELECT COUNT(*) FROM documents WHERE site_id = ?"),
            "chunks": one("SELECT COUNT(*) FROM chunks WHERE site_id = ?"),
            "daily": [dict(r) for r in daily],
            "usage_today": db.count_usage(conn),
            "daily_limit": config.DAILY_MESSAGE_LIMIT,
        }


@app.get("/api/admin/sites/{site_id}/documents")
def admin_documents(site_id: str, _: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = conn.execute("""
            SELECT d.*, (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id) chunks
            FROM documents d WHERE d.site_id = ? ORDER BY d.created_at DESC, d.id""", (site_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/documents/{doc_id}/chunks")
def admin_chunks(doc_id: int, _: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = conn.execute("SELECT id, heading, url, text FROM chunks WHERE document_id = ? ORDER BY id", (doc_id,)).fetchall()
    return [dict(r) for r in rows]


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@app.post("/api/admin/sites/{site_id}/documents/upload")
async def admin_upload(site_id: str, file: UploadFile = File(...), _: str = Depends(require_admin)):
    get_site_or_404(site_id)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (5 MB max)")
    name = file.filename or "document.txt"
    if not name.lower().endswith((".pdf", ".txt", ".md", ".html", ".htm")):
        raise HTTPException(400, "Supported files: PDF, TXT, Markdown, HTML")
    try:
        doc = await run_in_threadpool(ingest.parse_upload, data, name)
        return await run_in_threadpool(knowledge.add_document, site_id, doc, f"file:{name}")
    except ValueError as e:
        raise HTTPException(400, str(e))


class UrlImport(BaseModel):
    url: str
    follow_links: bool = False


@app.post("/api/admin/sites/{site_id}/documents/url")
async def admin_import_url(site_id: str, req: UrlImport, _: str = Depends(require_admin)):
    get_site_or_404(site_id)
    urls = [req.url]
    if req.follow_links:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers={"User-Agent": ingest.USER_AGENT}) as c:
            resp = await c.get(req.url)
        urls = [str(resp.url)] + [u for u in ingest.same_site_links(resp.text, str(resp.url)) if u != str(resp.url)]
    imported, errors = [], []
    for url in urls[:30]:
        try:
            doc = await ingest.fetch_page(url)
            imported.append(await run_in_threadpool(knowledge.add_document, site_id, doc, url))
        except Exception as e:
            errors.append({"url": url, "error": str(e)[:200]})
    if not imported:
        raise HTTPException(400, errors[0]["error"] if errors else "Nothing imported")
    return {"imported": imported, "errors": errors}


@app.delete("/api/admin/documents/{doc_id}")
def admin_delete_document(doc_id: int, _: str = Depends(require_admin)):
    if not knowledge.delete_document(doc_id):
        raise HTTPException(404, "Document not found")
    return {"ok": True}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


@app.post("/api/admin/sites/{site_id}/search")
async def admin_search(site_id: str, req: SearchRequest, _: str = Depends(require_viewer)):
    """Retrieval debugger: which passages would the assistant read for this question?"""
    hits = await find_passages(get_site_or_404(site_id), req.query)
    return [{"heading": h.heading, "url": h.url, "text": h.text, "score": round(h.score, 3),
             "similarity": round(h.similarity, 3), "keyword_score": round(h.keyword_score, 2)} for h in hits]


@app.get("/api/admin/sites/{site_id}/conversations")
def admin_conversations(site_id: str, role: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = conn.execute("""
            SELECT c.*,
              (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.role = 'user') questions,
              (SELECT MAX(handoff) FROM messages m WHERE m.conversation_id = c.id) handoff,
              (SELECT content FROM messages m WHERE m.conversation_id = c.id AND m.role = 'user' ORDER BY m.id LIMIT 1) first_question
            FROM conversations c WHERE c.site_id = ? AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)
            ORDER BY c.updated_at DESC LIMIT 200""", (site_id,)).fetchall()
    out = [dict(r) for r in rows]
    if role != "admin":
        for r in out:
            r["first_question"] = redact(r["first_question"])
    return out


@app.get("/api/admin/conversations/{conv_id}")
def admin_conversation(conv_id: str, role: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, handoff, created_at FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)
        ).fetchall()
    msgs = [{**dict(r), "sources": json.loads(r["sources"])} for r in rows]
    if role != "admin":
        for m in msgs:
            m["content"] = redact(m["content"])
    return msgs


@app.get("/api/admin/sites/{site_id}/leads")
def admin_leads(site_id: str, role: str = Depends(require_viewer)):
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE site_id = ? ORDER BY created_at DESC LIMIT 500", (site_id,))]
    if role != "admin":
        for r in rows:
            r["email"] = mask_email(r["email"])
            r["name"] = (r["name"][:1] + "•••") if r["name"] else ""
            r["message"] = redact(r["message"])
    return rows


# ================================================================ static files


@app.get("/widget.js", include_in_schema=False)
def widget_js():
    path = config.WIDGET_DIST / "widget.js"
    if not path.exists():
        raise HTTPException(404, "Widget not built: cd widget && npm install && npm run build")
    return FileResponse(path, media_type="application/javascript", headers={"Cache-Control": "public, max-age=300"})


@app.get("/admin", include_in_schema=False)
def admin_root():
    return RedirectResponse("/admin/")


@app.get("/admin/{path:path}", include_in_schema=False)
def admin_spa(path: str):
    dist = config.ADMIN_DIST
    if not (dist / "index.html").exists():
        raise HTTPException(404, "Admin not built: cd admin && npm install && npm run build")
    file = (dist / path).resolve()
    if path and file.is_file() and file.is_relative_to(dist.resolve()):
        return FileResponse(file)
    return FileResponse(dist / "index.html")


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}


# The demo shop is served at the root, so the widget and its API share one origin.
app.mount("/", StaticFiles(directory=config.DEMO_SITE_DIR, html=True), name="demo")
