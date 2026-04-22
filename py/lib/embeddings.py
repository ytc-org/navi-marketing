"""OpenAI embeddings wrapper for semantic similarity.

Used by the internal_link_recommendations workflow to rank sitemap URLs by
semantic closeness to the target page's topics and entities.

Pattern:
- Batch embed all candidate URL labels (title + slug-derived phrase) in a single call
- Embed the target page's topic phrases in a single call
- Compute cosine similarity for every (topic, url) pair
- For each URL, keep the MAX similarity across topics (a URL that strongly matches
  one topic is more useful than one that weakly matches many)
- Return the top N URLs by that score

Cheap by design: we embed short strings (titles + slug phrases), not full page content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import openai


EMBED_MODEL = "text-embedding-3-small"


@dataclass
class RankedUrl:
    """A sitemap URL with its best similarity score and the topic that drove it."""

    url: str
    label: str
    score: float
    matched_topic: str


def _get_client() -> openai.OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file. "
            "Get one at https://platform.openai.com/api-keys"
        )
    return openai.OpenAI(api_key=api_key)


def embed_batch(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Embed a batch of strings. Returns one vector per input, preserving order.

    The OpenAI API allows up to 2048 inputs per call for text-embedding-3-small,
    which is plenty for typical sitemaps. For larger sites, chunk and combine.
    """
    if not texts:
        return []
    client = _get_client()

    # Replace empty strings with a single space — the API rejects empty input
    cleaned = [t if t.strip() else " " for t in texts]

    # Batch in chunks of 2000 to stay under the limit comfortably
    all_vectors: list[list[float]] = []
    for i in range(0, len(cleaned), 2000):
        chunk = cleaned[i:i + 2000]
        response = client.embeddings.create(model=model, input=chunk)
        all_vectors.extend(item.embedding for item in response.data)
    return all_vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Assumes non-zero magnitude."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(y * y for y in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def rank_urls_by_similarity(
    topics: list[str],
    urls: list[tuple[str, str]],
    top_n: int = 30,
) -> list[RankedUrl]:
    """Rank sitemap URLs by semantic similarity to a list of topic phrases.

    Args:
        topics: List of topic/entity phrases extracted from the target page.
        urls: List of (url, label) tuples. Label is a short descriptor of the page
              (title, or a human-readable version of the slug).
        top_n: How many URLs to return, ranked by max-topic similarity.

    Returns:
        Top-N RankedUrl records, sorted descending by score.
    """
    if not topics or not urls:
        return []

    # Embed everything in two API calls
    topic_vectors = embed_batch(topics)
    url_labels = [label for _, label in urls]
    url_vectors = embed_batch(url_labels)

    ranked: list[RankedUrl] = []
    for (url, label), url_vec in zip(urls, url_vectors):
        # Best similarity across all topics
        best_score = -1.0
        best_topic = ""
        for topic, topic_vec in zip(topics, topic_vectors):
            score = cosine_similarity(topic_vec, url_vec)
            if score > best_score:
                best_score = score
                best_topic = topic
        ranked.append(RankedUrl(url=url, label=label, score=best_score, matched_topic=best_topic))

    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked[:top_n]
