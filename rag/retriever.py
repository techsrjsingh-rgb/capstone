"""
retriever.py — TF-IDF Knowledge Retriever
==========================================
Retrieves the most relevant past fraud cases given a query string.
Uses TF-IDF (term frequency–inverse document frequency) — a simple
bag-of-words similarity measure that requires no API calls.

Usage:
    retriever = FraudCaseRetriever()
    cases = retriever.retrieve("large transfer international location", top_k=3)
"""

import math
import re
from collections import Counter

from core.data import SAMPLE_TRANSACTIONS


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_document(txn: dict) -> str:
    """Convert a transaction dict into a searchable text document."""
    return (
        f"{txn.get('transaction_type', '')} "
        f"{txn.get('location', '')} "
        f"amount {txn.get('amount', '')} "
        f"customer {txn.get('customer_id', '')}"
    )


class FraudCaseRetriever:
    """
    TF-IDF retriever over the sample transaction corpus.
    Builds an in-memory index on first instantiation.
    """

    def __init__(self, transactions: list[dict] | None = None):
        self._corpus = transactions or SAMPLE_TRANSACTIONS
        self._documents = [_build_document(t) for t in self._corpus]
        self._tokenized = [_tokenize(d) for d in self._documents]
        self._idf = self._compute_idf()

    def _compute_idf(self) -> dict[str, float]:
        """Compute inverse document frequency for every term in the corpus."""
        n = len(self._tokenized)
        df: dict[str, int] = {}
        for tokens in self._tokenized:
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1
        return {term: math.log(n / (1 + freq)) for term, freq in df.items()}

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        """Compute TF-IDF vector for a list of tokens."""
        tf = Counter(tokens)
        total = len(tokens) or 1
        return {
            term: (count / total) * self._idf.get(term, 0.0)
            for term, count in tf.items()
        }

    def _cosine_similarity(self, vec_a: dict, vec_b: dict) -> float:
        """Cosine similarity between two TF-IDF vectors."""
        common = set(vec_a) & set(vec_b)
        if not common:
            return 0.0
        dot = sum(vec_a[t] * vec_b[t] for t in common)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Return the top_k most similar transactions for the given query.

        Parameters:
            query  — natural language or keyword string describing the fraud scenario
            top_k  — number of results to return (default 3)

        Returns:
            List of dicts: {"transaction": <txn dict>, "score": <float>, "document": <str>}
        """
        query_tokens = _tokenize(query)
        query_vec = self._tfidf_vector(query_tokens)

        scores = []
        for i, tokens in enumerate(self._tokenized):
            doc_vec = self._tfidf_vector(tokens)
            sim = self._cosine_similarity(query_vec, doc_vec)
            scores.append((sim, i))

        scores.sort(reverse=True)
        return [
            {
                "transaction": self._corpus[i],
                "score": round(sim, 4),
                "document": self._documents[i],
            }
            for sim, i in scores[:top_k]
            if sim > 0
        ]


# Module-level singleton
retriever = FraudCaseRetriever()
