import asyncio

import pytest

from app import db, llm, main, retrieval

# Realistic visitor questions -> the passage the assistant must find first.
CASES = [
    ("Vous livrez en Belgique ?", "Livraison"),
    ("Do you ship to Switzerland?", "Livraison"),  # English question, French content
    ("Quelle bougie pour la chambre ?", "Lavande de Provence"),
    ("Je peux retourner une bougie ?", "Retours et remboursements"),
    ("ma bougie est arrivée cassée", "Retours et remboursements"),
    ("atelier le dimanche ?", "L'atelier-boutique"),
    ("bougie figue prix", "Figue & Cèdre"),
    ("mon chat risque quelque chose ?", "Les bougies parfumées sont-elles dangereuses pour les animaux ?"),
    ("vous faites des bougies avec logo pour un mariage", "Cadeaux d'entreprise et événements"),
]


# A wider set of realistic questions. What matters for the answer is that the right
# passage is among the ones the LLM reads (top 5); accepted answers are listed per question.
RECALL_CASES = [
    ("Vous livrez en Belgique ?", {"Livraison"}),
    ("Do you ship to Switzerland?", {"Livraison"}),
    ("Vous envoyez à Bruxelles ?", {"Livraison"}),
    ("c combien la livraison pour lyon", {"Livraison", "Livraison & retours"}),
    ("Quelle bougie pour la chambre ?", {"Lavande de Provence"}),
    ("bougie pour dormir", {"Lavande de Provence"}),
    ("Je peux retourner une bougie ?", {"Retours et remboursements"}),
    ("ma commande est arrivée cassée", {"Retours et remboursements"}),
    ("atelier le dimanche ?", {"L'atelier-boutique"}),
    ("vous êtes ouverts le lundi ?", {"L'atelier-boutique"}),
    ("bougie figue prix", {"Figue & Cèdre"}),
    ("mon chat risque quelque chose ?", {"Les bougies parfumées sont-elles dangereuses pour les animaux ?"}),
    ("vous faites des bougies avec logo pour un mariage", {"Cadeaux d'entreprise et événements"}),
    ("cadeau pour ma mère", {"Proposez-vous un emballage cadeau ?", "Coffret découverte"}),
    ("vous acceptez paypal ?", {"Paiement et cartes cadeaux"}),
    ("combien coûte un atelier ?", {"Atelier création de bougie"}),
    ("is it vegan?", {"Vos bougies sont-elles vegan et sans paraffine ?", "La collection"}),
    ("je peux rapporter mon pot vide ?", {"Recharge en atelier", "Pots réutilisables"}),
]


# Questions in another language than the site's: searched as asked and translated by
# the LLM (mocked here with the query it would write).
TRANSLATED_CASES = [
    ("Do you have a vanilla candle?", "bougie vanille", "Bois de santal"),
    ("Do you ship to Belgium?", "livraison Belgique", "Livraison"),
]


def find_passages(question: str) -> list[retrieval.Hit]:
    with db.connect() as conn:
        site = db.get_site(conn, "atelier-lumen")
    return asyncio.run(main.find_passages(site, question))


def test_recall_at_5_on_realistic_questions(client):
    missed = [q for q, accepted in RECALL_CASES
              if not accepted & {h.heading for h in retrieval.search("atelier-lumen", q, 5)}]
    # Known miss: "bougie pour dormir" needs world knowledge (lavender helps sleep) that the site never states.
    assert len(missed) <= 1, missed


@pytest.mark.parametrize("question,expected", CASES)
def test_demo_questions_find_the_right_passage(client, question, expected):
    hits = retrieval.search("atelier-lumen", question, 3)
    assert hits[0].heading == expected, [h.heading for h in hits]


@pytest.mark.parametrize("question,translation,expected", TRANSLATED_CASES)
def test_questions_in_another_language_are_also_searched_translated(client, fake_translation, question, translation, expected):
    fake_translation.table[question] = translation
    hits = find_passages(question)
    assert fake_translation.asked == [question]
    assert hits[0].heading == expected, [h.heading for h in hits]
    assert hits[0].score >= 0.5  # strong enough to be linked as a source (untranslated: about 0.3)


def test_questions_in_the_site_language_are_not_translated(client, fake_translation):
    hits = find_passages("Vous avez une bougie à la vanille ?")
    assert hits[0].heading == "Bois de santal"
    assert fake_translation.asked == []


def test_failed_translation_falls_back_to_the_question(client, monkeypatch):
    async def broken(*_):
        raise RuntimeError("API down")

    monkeypatch.setattr(llm, "translate_query", broken)
    assert find_passages("Do you ship to Switzerland?")[0].heading == "Livraison"


def test_language_guess():
    assert not retrieval.is_in_language("Do you have a vanilla candle?", "fr")
    assert not retrieval.is_in_language("is it vegan?", "fr")
    assert not retrieval.is_in_language("هل تشحنون إلى بلجيكا؟", "fr")
    assert retrieval.is_in_language("Vous livrez en Belgique ?", "fr")
    assert retrieval.is_in_language("c combien la livraison pour lyon", "fr")
    assert retrieval.is_in_language("bougie figue prix", "fr")  # no clear sign: no extra LLM call
    assert retrieval.is_in_language("Do you ship to Belgium?", "en")
    assert not retrieval.is_in_language("Vous livrez en Belgique ?", "en")


def test_off_topic_questions_score_low(client):
    hits = retrieval.search("atelier-lumen", "quelle est la capitale du Japon", 3)
    assert hits[0].score < 0.3


def test_tokenizer_folds_accents_plurals_and_feminine_forms():
    assert retrieval.tokenize("Arrivée cassée") == retrieval.tokenize("arrivé cassé")
    assert retrieval.tokenize("bougies") == retrieval.tokenize("bougie")
    assert "pour" not in retrieval.tokenize("une bougie pour la chambre")
