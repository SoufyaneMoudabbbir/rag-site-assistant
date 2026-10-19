"""Create the demo site (Atelier Lumen) and import its pages on first start."""

import json

from app import config, db, knowledge
from app.ingest import parse_html

DEMO_SITE = {
    "id": "atelier-lumen",
    "name": "Atelier Lumen",
    "language": "fr",
    "color": "#b5562b",
    "welcome": "Bonjour ! Je suis l'assistant d'Atelier Lumen. Je peux répondre à vos questions sur nos bougies, la livraison, les retours ou les ateliers.",
    "suggestions": [
        "Vous livrez en Belgique ?",
        "Quelle bougie pour la chambre ?",
        "Comment se passe un atelier ?",
        "Je peux retourner une bougie ?",
    ],
    "instructions": "Ton ton est chaleureux et simple, comme un artisan qui conseille en boutique.",
}

DEMO_PAGES = ["index.html", "livraison-retours.html", "ateliers.html", "faq.html"]


def seed() -> None:
    with db.connect() as conn:
        exists = conn.execute("SELECT 1 FROM sites WHERE id = ?", (DEMO_SITE["id"],)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO sites (id, name, language, color, welcome, suggestions, instructions, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (DEMO_SITE["id"], DEMO_SITE["name"], DEMO_SITE["language"], DEMO_SITE["color"],
                 DEMO_SITE["welcome"], json.dumps(DEMO_SITE["suggestions"], ensure_ascii=False),
                 DEMO_SITE["instructions"], db.now()),
            )
        has_docs = conn.execute("SELECT 1 FROM documents WHERE site_id = ?", (DEMO_SITE["id"],)).fetchone()
    if has_docs:
        return
    for page in DEMO_PAGES:
        path = config.DEMO_SITE_DIR / page
        if path.exists():
            doc = parse_html(path.read_text(encoding="utf-8"), f"/{page}")
            knowledge.add_document(DEMO_SITE["id"], doc, source=f"/{page}")
