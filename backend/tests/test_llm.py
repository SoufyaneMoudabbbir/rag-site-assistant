from app.llm import HANDOFF_MARKER, MarkerFilter, build_messages
from app.retrieval import Hit


def run(pieces: list[str]) -> tuple[str, bool]:
    f = MarkerFilter()
    out = "".join(f.feed(p) for p in pieces) + f.flush()
    return out, f.found


def test_marker_is_removed_even_when_split_across_tokens():
    text, found = run(["Je transmets à l'équipe. [", "[HAND", "OFF]", "]"])
    assert text == "Je transmets à l'équipe. "
    assert found


def test_text_without_marker_passes_through_unchanged():
    text, found = run(["Prix : 32 € [voir ", "fiche] ", "merci"])
    assert text == "Prix : 32 € [voir fiche] merci"
    assert not found


def test_prompt_contains_passages_question_and_site_rules():
    site = {"name": "Atelier Lumen", "instructions": "Vouvoyer."}
    hit = Hit(1, "Livraison", "/l#x", "Livraison\n9,90 € en Belgique", "Livraison", 0.8, 3.0, 0.9)
    messages = build_messages(site, [hit], [{"role": "user", "content": "avant"}], "Vous livrez en Belgique ?")
    assert messages[0]["role"] == "system"
    assert "Atelier Lumen" in messages[0]["content"] and "Vouvoyer." in messages[0]["content"]
    assert HANDOFF_MARKER in messages[0]["content"]
    assert messages[1]["content"] == "avant"
    assert "9,90 € en Belgique" in messages[-1]["content"]
    assert messages[-1]["content"].endswith("Vous livrez en Belgique ?")
