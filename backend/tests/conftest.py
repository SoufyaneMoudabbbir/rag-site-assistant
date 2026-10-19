import os
import tempfile

import pytest

# Isolated settings, set before the app is imported (config reads them once).
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="site-assistant-test-")
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["DEMO_PASSWORD"] = "demo"
os.environ["LLM_API_KEY"] = "test-key"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  # runs startup: database, embedding model, demo seed
        yield c


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the real LLM with a scripted reply streamed in small pieces."""
    from app import llm

    replies: list[str] = []

    async def stream(_messages):
        text = replies.pop(0) if replies else "Réponse de test."
        for i in range(0, len(text), 4):
            yield text[i:i + 4]

    monkeypatch.setattr(llm, "stream_answer", stream)
    return replies


@pytest.fixture
def admin_headers(client):
    token = client.post("/api/admin/login", json={"password": "test-admin-password"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(client):
    token = client.post("/api/admin/login", json={"password": "demo"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
