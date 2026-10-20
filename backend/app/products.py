"""Product cards: the products an answer talks about, with photo, price and link."""

import re

from app import db
from app.retrieval import _fold

MAX_CARDS = 3


def _normalize(text: str) -> str:
    """Lowercase, no accents, "&" read as "et", punctuation as spaces."""
    text = _fold(text).replace("&", " et ")
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


def mentioned_products(site_id: str, answer: str) -> list[dict]:
    """Products named in the answer, in the order the answer mentions them.
    Matching what the answer says (not what was retrieved) means a card never
    appears under an answer about delivery or returns."""
    text = _normalize(answer)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name, price, currency, image, url FROM products WHERE site_id = ?", (site_id,)
        ).fetchall()
    found = []
    for row in rows:
        pos = text.find(_normalize(row["name"]))
        if pos >= 0:
            found.append((pos, dict(row)))
    return [p for _, p in sorted(found, key=lambda x: x[0])][:MAX_CARDS]
