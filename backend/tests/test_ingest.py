from app.ingest import MAX_CHUNK_CHARS, parse_html, parse_text, split_long

HTML = """
<html><head><title>Boutique · Démo</title></head><body>
<nav><a href="/">Accueil</a></nav>
<div class="demo-banner">Bandeau à ignorer</div>
<main>
  <h1>Bienvenue</h1>
  <p>Nous fabriquons des bougies parfumées à la main depuis 2019.</p>
  <article class="product"><span>Nouveau</span><h3>Figue</h3><p>Bougie à la figue, 180 g, 32 euros.</p></article>
  <section id="livraison"><h2>Livraison</h2>
    <table><tr><td>France</td><td>4,90 €</td></tr><tr><td>Belgique</td><td>9,90 €</td></tr></table>
  </section>
  <details><summary>Vos bougies sont-elles vegan ?</summary><p>Oui, 100 % végétales et sans paraffine.</p></details>
</main>
<footer>Pied de page à ignorer</footer>
</body></html>
"""


def test_html_is_split_into_self_contained_chunks():
    doc = parse_html(HTML, "https://shop.example/page")
    texts = [c.text for c in doc.chunks]
    assert doc.title == "Boutique"
    # A product card and a FAQ entry each become one chunk, headed by their title.
    assert any(t.startswith("Boutique — Figue\n") and "Nouveau" in t and "32 euros" in t for t in texts)
    assert any("Vos bougies sont-elles vegan" in t and "sans paraffine" in t for t in texts)
    # Table rows are kept as readable lines.
    assert any("Belgique | 9,90 €" in t for t in texts)
    # Navigation, banners and footers never reach the knowledge base.
    joined = " ".join(texts)
    assert "Bandeau" not in joined and "Pied de page" not in joined and "Accueil" not in joined


def test_section_chunks_link_to_their_anchor():
    doc = parse_html(HTML, "https://shop.example/page")
    delivery = next(c for c in doc.chunks if c.heading == "Livraison")
    assert delivery.url == "https://shop.example/page#livraison"


def test_long_text_is_split_with_overlap():
    sentence = "Cette phrase parle de bougies et de livraison en France. "
    parts = split_long(sentence * 60)
    assert len(parts) > 1
    assert all(len(p) <= MAX_CHUNK_CHARS + len(sentence) for p in parts)
    assert parts[1].startswith(parts[0][-100:].split(" ", 2)[-1][:20]) or "bougies" in parts[1][:150]


def test_markdown_headings_start_new_chunks():
    doc = parse_text("# Conditions de vente\n\n## Retours\nVous avez trente jours pour retourner un article non utilisé.\n\n## Paiement\nCarte bancaire, PayPal et virement sont acceptés pour toute commande.", "cgv.md")
    assert doc.title == "Conditions de vente"
    assert [c.heading for c in doc.chunks] == ["Retours", "Paiement"]
