"""Hybrid retrieval: semantic search (embeddings) + keyword search (BM25),
merged as a weighted score.

Embeddings understand paraphrases and other languages ("Vous envoyez à
Bruxelles ?" -> the delivery section); BM25 catches exact words such as
product names and prices. Each site's index lives in memory and is rebuilt
when its documents change.
"""

import math
import re
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass

import numpy as np

from app import db, embeddings

SEMANTIC_WEIGHT = 0.65  # the rest goes to keywords, relative to the best keyword match

STOPWORDS = set("""
a au aux avec ce ces dans de des du elle en et est il ils je la le les leur lui ma mais me mes moi mon ne nos notre
nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y c d j l m n s t
est-ce quel quelle quels quelles comment combien puis peux peut faire avez avoir etre suis sont
the a an and are as at be by can do does for from how i in is it my of on or our that the to we what when where which
who will with you your
""".split())


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9]+", _fold(text)):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        # Light French/English stemming: "bougies" ~ "bougie", "cassée" ~ "cassé".
        if len(tok) > 4 and tok.endswith(("s", "x")):
            tok = tok[:-1]
        while len(tok) > 4 and tok.endswith("e"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


# Frequent words that tell a few languages apart. Only used to skip translating a
# question that is already in the site's language, so a rough guess is enough.
LANGUAGE_WORDS = {
    "fr": set("""je tu il nous vous ils le la les un une des du est sont avez avec pour dans sur pas que qui quel
        quelle quels quelles ce cette mon ma mes votre vos bonjour merci oui non combien comment livrez faites peux""".split()),
    "en": set("""i you he we they the is are do does did have has an and with for in on of to not it what which who how
        where when this that my your our hello thanks yes no any can ship much""".split()),
    "es": set("""yo usted ustedes el los las una es son tienen hay con por para que como cuanto donde envian hola
        gracias si vela velas""".split()),
    "de": set("""ich du sie wir ihr der die das ein eine ist sind haben habt mit fur und nicht wie wo wann kerze
        kerzen hallo danke ja nein auch""".split()),
}


def is_in_language(text: str, language: str) -> bool:
    """Light guess: is the text written in this language? Text without clear signs
    (a product name, a few keywords) counts as yes."""
    letters = [c for c in text if c.isalpha()]
    non_latin = sum(not unicodedata.name(c, "").startswith("LATIN") for c in letters)
    if language in LANGUAGE_WORDS and non_latin > len(letters) / 2:
        return False  # Arabic, Cyrillic, Chinese... on a site written in Latin letters
    words = re.findall(r"[a-z]+", _fold(text))
    counts = {lang: sum(w in vocab for w in words) for lang, vocab in LANGUAGE_WORDS.items()}
    others = max((n for lang, n in counts.items() if lang != language), default=0)
    return others <= counts.get(language, 0)


@dataclass
class Hit:
    chunk_id: int
    heading: str
    url: str | None
    text: str
    document_title: str
    similarity: float  # cosine similarity of the embedding, 0..1
    keyword_score: float
    score: float  # weighted semantic + keyword score used for ordering


class SiteIndex:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.matrix = np.vstack([embeddings.from_blob(r["embedding"]) for r in rows]) if rows else None
        self.docs_tokens = [tokenize(r["text"]) for r in rows]
        self.doc_freq = Counter(t for toks in self.docs_tokens for t in set(toks))
        self.avg_len = (sum(len(t) for t in self.docs_tokens) / len(rows)) if rows else 0

    def bm25(self, query_tokens: list[str], k1: float = 1.4, b: float = 0.75) -> np.ndarray:
        n = len(self.rows)
        scores = np.zeros(n, dtype=np.float32)
        for i, toks in enumerate(self.docs_tokens):
            tf = Counter(toks)
            for q in set(query_tokens):
                if q not in tf:
                    continue
                idf = math.log(1 + (n - self.doc_freq[q] + 0.5) / (self.doc_freq[q] + 0.5))
                f = tf[q]
                scores[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(toks) / (self.avg_len or 1)))
        return scores

    def search(self, query: str, k: int) -> list[Hit]:
        if not self.rows:
            return []
        q_vec = embeddings.embed([query])[0]
        similarity = self.matrix @ q_vec
        keyword = self.bm25(tokenize(query))

        best_keyword = keyword.max()
        keyword_norm = keyword / best_keyword if best_keyword > 0 else keyword
        fused = SEMANTIC_WEIGHT * similarity + (1 - SEMANTIC_WEIGHT) * keyword_norm

        hits = []
        for idx in np.argsort(-fused)[:k]:
            r = self.rows[idx]
            hits.append(Hit(
                chunk_id=r["id"], heading=r["heading"], url=r["url"], text=r["text"],
                document_title=r["title"], similarity=float(similarity[idx]),
                keyword_score=float(keyword[idx]), score=float(fused[idx]),
            ))
        return hits


_indexes: dict[str, SiteIndex] = {}
_lock = threading.Lock()


def get_index(site_id: str) -> SiteIndex:
    with _lock:
        if site_id not in _indexes:
            with db.connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT c.id, c.heading, c.url, c.text, c.embedding, d.title "
                    "FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.site_id = ? ORDER BY c.id",
                    (site_id,),
                )]
            _indexes[site_id] = SiteIndex(rows)
        return _indexes[site_id]


def invalidate(site_id: str) -> None:
    with _lock:
        _indexes.pop(site_id, None)


def search(site_id: str, query: str, k: int = 5) -> list[Hit]:
    return get_index(site_id).search(query, k)


def merge(*results: list[Hit], k: int) -> list[Hit]:
    """Combine several searches for one question (original and translated): best score per passage."""
    best: dict[int, Hit] = {}
    for hits in results:
        for h in hits:
            if h.chunk_id not in best or h.score > best[h.chunk_id].score:
                best[h.chunk_id] = h
    return sorted(best.values(), key=lambda h: -h.score)[:k]
