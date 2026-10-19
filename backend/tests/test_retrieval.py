import pytest

from app import retrieval

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


@pytest.mark.parametrize("question,expected", CASES)
def test_demo_questions_find_the_right_passage(client, question, expected):
    hits = retrieval.search("atelier-lumen", question, 3)
    assert hits[0].heading == expected, [h.heading for h in hits]


def test_off_topic_questions_score_low(client):
    hits = retrieval.search("atelier-lumen", "quelle est la capitale du Japon", 3)
    assert hits[0].score < 0.3


def test_tokenizer_folds_accents_plurals_and_feminine_forms():
    assert retrieval.tokenize("Arrivée cassée") == retrieval.tokenize("arrivé cassé")
    assert retrieval.tokenize("bougies") == retrieval.tokenize("bougie")
    assert "pour" not in retrieval.tokenize("une bougie pour la chambre")
