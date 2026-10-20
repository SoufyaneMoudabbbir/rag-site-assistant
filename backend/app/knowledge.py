"""Add and remove documents from a site's knowledge base."""

from app import db, embeddings, retrieval
from app.ingest import ParsedDocument


def add_document(site_id: str, doc: ParsedDocument, source: str) -> dict:
    if not doc.chunks:
        raise ValueError("No readable text found in this document")
    vectors = embeddings.embed([c.text for c in doc.chunks])
    with db.connect() as conn:
        # Re-importing the same source replaces the previous version.
        conn.execute("DELETE FROM documents WHERE site_id = ? AND source = ?", (site_id, source))
        cur = conn.execute(
            "INSERT INTO documents (site_id, title, source, kind, chars, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (site_id, doc.title, source, doc.kind, doc.chars, db.now()),
        )
        doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO chunks (document_id, site_id, heading, url, text, embedding) VALUES (?, ?, ?, ?, ?, ?)",
            [(doc_id, site_id, c.heading, c.url, c.text, embeddings.to_blob(v)) for c, v in zip(doc.chunks, vectors)],
        )
        conn.executemany(
            "INSERT INTO products (document_id, site_id, name, price, currency, image, url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(doc_id, site_id, pr.name, pr.price, pr.currency, pr.image, pr.url, pr.description) for pr in doc.products],
        )
    retrieval.invalidate(site_id)
    return {"id": doc_id, "title": doc.title, "chunks": len(doc.chunks), "chars": doc.chars, "products": len(doc.products)}


def delete_document(doc_id: int) -> str | None:
    with db.connect() as conn:
        row = conn.execute("SELECT site_id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    retrieval.invalidate(row["site_id"])
    return row["site_id"]
