import json

from app import config, security


def chat(client, message, conversation_id=None, **headers):
    r = client.post("/api/chat", json={"site_id": "atelier-lumen", "message": message, "conversation_id": conversation_id}, headers=headers)
    if r.status_code != 200:
        return r.status_code, {}
    events = {}
    text = ""
    for block in r.text.strip().split("\n\n"):
        name = block.split("\n")[0].removeprefix("event: ")
        data = json.loads(block.split("\n", 1)[1].removeprefix("data: "))
        if name == "token":
            text += data["t"]
        else:
            events[name] = data
    events["text"] = text
    return 200, events


def test_widget_config(client):
    cfg = client.get("/api/sites/atelier-lumen/config").json()
    assert cfg["name"] == "Atelier Lumen" and cfg["suggestions"]
    assert client.get("/api/sites/nope/config").status_code == 404


def test_chat_streams_answer_with_sources(client, fake_llm):
    fake_llm.append("Oui, la livraison en Belgique coûte **9,90 €**.")
    status, ev = chat(client, "Vous livrez en Belgique ?")
    assert status == 200
    assert ev["text"] == "Oui, la livraison en Belgique coûte **9,90 €**."
    assert ev["start"]["sources"][0]["title"] == "Livraison"
    assert ev["done"]["handoff"] is False


def test_question_in_another_language_finds_sources_through_translation(client, fake_llm, fake_translation):
    fake_translation.table["Do you have a vanilla candle?"] = "bougie vanille"
    fake_llm.append("Yes, **Bois de santal** has Madagascar vanilla.")
    _, ev = chat(client, "Do you have a vanilla candle?")
    assert ev["start"]["sources"][0]["title"] == "Bois de santal"
    assert ev["text"] == "Yes, **Bois de santal** has Madagascar vanilla."


def test_handoff_marker_is_hidden_and_flagged(client, fake_llm):
    fake_llm.append("Je transmets votre demande de devis à l'équipe. [[HANDOFF]]")
    _, ev = chat(client, "Je veux 50 bougies avec mon logo")
    assert "HANDOFF" not in ev["text"]
    assert ev["done"]["handoff"] is True


def test_conversation_history_is_kept(client, fake_llm):
    fake_llm.extend(["Premier.", "Second."])
    _, first = chat(client, "Vous livrez en Belgique ?")
    conv = first["start"]["conversation_id"]
    _, second = chat(client, "et en Suisse ?", conv)
    assert second["start"]["conversation_id"] == conv


def test_lead_validation(client):
    ok = client.post("/api/leads", json={"site_id": "atelier-lumen", "email": "client@example.com", "name": "Client", "message": "Devis"})
    assert ok.status_code == 200
    bad = client.post("/api/leads", json={"site_id": "atelier-lumen", "email": "not-an-email"})
    assert bad.status_code == 400


def test_login_roles(client):
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/admin/login", json={"password": "demo"}).json()["role"] == "viewer"
    assert client.get("/api/admin/sites").status_code == 401


def test_viewer_is_read_only_and_sees_masked_data(client, viewer_headers):
    assert client.get("/api/admin/sites", headers=viewer_headers).status_code == 200
    upload = client.post("/api/admin/sites/atelier-lumen/documents/upload", headers=viewer_headers,
                         files={"file": ("x.txt", b"Un texte assez long pour faire au moins un passage.")})
    assert upload.status_code == 403
    leads = client.get("/api/admin/sites/atelier-lumen/leads", headers=viewer_headers).json()
    assert leads and all("example.com" not in lead["email"] for lead in leads)


def test_admin_can_add_search_and_delete_a_document(client, admin_headers):
    content = "# Horaires d'été\nEn juillet et en août, l'atelier ouvre aussi le dimanche de 10 h à 13 h.".encode()
    r = client.post("/api/admin/sites/atelier-lumen/documents/upload", headers=admin_headers, files={"file": ("ete.md", content)})
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]
    hits = client.post("/api/admin/sites/atelier-lumen/search", headers=admin_headers, json={"query": "ouvert le dimanche en août ?"}).json()
    assert hits[0]["heading"].startswith("Horaires d'été")
    assert client.delete(f"/api/admin/documents/{doc_id}", headers=admin_headers).status_code == 200
    hits = client.post("/api/admin/sites/atelier-lumen/search", headers=admin_headers, json={"query": "ouvert le dimanche en août ?"}).json()
    assert not hits[0]["heading"].startswith("Horaires d'été")


def test_allowed_origins_are_enforced(client, admin_headers, fake_llm):
    site = client.get("/api/admin/sites/atelier-lumen", headers=admin_headers).json()
    client.put("/api/admin/sites/atelier-lumen", headers=admin_headers, json={**site, "allowed_origins": "https://shop.example"})
    try:
        assert client.get("/api/sites/atelier-lumen/config", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/sites/atelier-lumen/config", headers={"Origin": "https://shop.example"}).status_code == 200
    finally:
        client.put("/api/admin/sites/atelier-lumen", headers=admin_headers, json={**site, "allowed_origins": "*"})


def test_rate_limit(client, fake_llm, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_MESSAGES", 2)
    security._hits.clear()
    assert chat(client, "Bonjour")[0] == 200
    assert chat(client, "Bonjour")[0] == 200
    assert chat(client, "Bonjour")[0] == 429
    security._hits.clear()


def test_redaction_hides_contact_details():
    text = security.redact("Écrivez-moi à jean.dupont@gmail.com ou au 06 12 34 56 78")
    assert "jean.dupont" not in text and "12 34" not in text


def test_products_named_in_the_answer_come_as_cards(client, fake_llm):
    fake_llm.append("Pour la chambre, je vous conseille **Lavande de Provence**, ou Figue et Cèdre si vous aimez le boisé.")
    _, ev = chat(client, "Quelle bougie pour la chambre ?")
    cards = ev["products"]["products"]
    assert [c["name"] for c in cards] == ["Lavande de Provence", "Figue & Cèdre"]  # in the order mentioned
    assert cards[0]["price"] == "28.00" and cards[0]["currency"] == "EUR"
    assert cards[0]["image"].endswith("images/lavande-provence.jpg")
    assert cards[0]["url"].endswith("#lavande-provence")


def test_no_cards_when_the_answer_names_no_product(client, fake_llm):
    fake_llm.append("La livraison en Belgique coûte 9,90 €.")
    _, ev = chat(client, "Vous livrez en Belgique ?")
    assert "products" not in ev


def test_sources_of_a_short_self_contained_follow_up(client, fake_llm):
    fake_llm.extend(["Je vous conseille Fleur d'oranger.", "Oui, 9,90 €.", "Oui, aussi 9,90 €."])
    _, first = chat(client, "Je cherche une bougie à offrir, ma mère aime les fleurs")
    conv = first["start"]["conversation_id"]
    # Short, but complete on its own: its sources must not come from the flower question.
    _, second = chat(client, "Vous livrez en Belgique ?", conv)
    assert second["start"]["sources"][0]["title"] == "Livraison"
    # Short and incomplete: still understood thanks to the previous question.
    _, third = chat(client, "et en Suisse ?", conv)
    assert third["start"]["sources"] and third["start"]["sources"][0]["title"] == "Livraison"
