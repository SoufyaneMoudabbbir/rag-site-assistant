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


def test_recall_at_5_on_realistic_questions(client):
    missed = [q for q, accepted in RECALL_CASES
              if not accepted & {h.heading for h in retrieval.search("atelier-lumen", q, 5)}]
    # Known miss: "bougie pour dormir" needs world knowledge (lavender helps sleep) that the site never states.
    assert len(missed) <= 1, missed


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
