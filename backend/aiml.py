"""Position-aware retrieval and Grok-powered answers for LoreFlow.

Only transcript chunks that have completely finished playing are ever sent to
Grok. Future chunks may be scored locally to detect a likely future-only
question, but their text is never included in the model prompt or response.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:  # pragma: no cover - lightweight fallback for minimal installs
    TfidfVectorizer = None
    cosine_similarity = None

logger = logging.getLogger(__name__)


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "who", "what", "where",
        "when", "why", "how", "does", "do", "did", "tell", "me", "about",
        "please", "can", "you", "i", "heard", "so", "far", "in", "on", "of",
        "to", "and", "or", "it", "this", "that", "my", "have", "has", "had",
        "she", "he", "they", "them", "her", "his", "their", "was", "were",
        "mr", "mrs", "miss", "ms", "sir", "lady", "lord",
    }
    return {token for token in _normalise(text).split() if len(token) > 1 and token not in stop}


def available_chunks(chunks: list[dict[str, Any]], position_sec: float) -> list[dict[str, Any]]:
    """Return only passages whose audio has completely finished playing."""
    return [chunk for chunk in chunks if float(chunk["end_sec"]) <= float(position_sec)]


def _score_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[tuple[float, dict[str, Any]]]:
    """Rank chunks against a query; scores are comparable within this call."""
    if not chunks:
        return []

    corpus = [chunk["text"] for chunk in chunks]
    if TfidfVectorizer is not None and cosine_similarity is not None:
        try:
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            matrix = vectorizer.fit_transform(corpus)
            query_vector = vectorizer.transform([question])
            scores = cosine_similarity(query_vector, matrix).ravel()
            ranked = sorted(
                ((float(score), chunk) for score, chunk in zip(scores, chunks)),
                key=lambda item: item[0],
                reverse=True,
            )
            return ranked
        except ValueError:
            # Empty vocabulary or a query with only stop words; use token overlap.
            pass

    query_terms = _tokens(question)
    ranked_fallback: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        terms = _tokens(chunk["text"])
        score = len(query_terms & terms) / max(1, len(query_terms))
        ranked_fallback.append((float(score), chunk))
    ranked_fallback.sort(key=lambda item: item[0], reverse=True)
    return ranked_fallback


def _relevant_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    top_k: int = 4,
    min_score: float = 0.025,
) -> list[dict[str, Any]]:
    return [
        chunk
        for score, chunk in _score_chunks(question, chunks)
        if score >= min_score
    ][:top_k]


def _future_only_match(
    question: str,
    all_chunks: list[dict[str, Any]],
    heard_chunks: list[dict[str, Any]],
) -> bool:
    """Detect whether the strongest matching evidence is still in the future.

    This compares scores over the complete local index, but does not return or
    pass any future passage text to the answer generator.
    """
    # Ignore honorifics and conversational filler for the future-only check.
    # Otherwise a repeated prefix such as "Mr." can outweigh an entity that
    # has already been introduced in an earlier passage.
    boundary_query = " ".join(sorted(_tokens(question))) or question
    ranked = _score_chunks(boundary_query, all_chunks)
    if not ranked:
        return False

    heard_ids = {chunk["id"] for chunk in heard_chunks}
    heard_score = max((score for score, chunk in ranked if chunk["id"] in heard_ids), default=0.0)
    future_score = max((score for score, chunk in ranked if chunk["id"] not in heard_ids), default=0.0)

    # Require a meaningful match and a clear advantage over heard passages.
    return future_score >= 0.075 and future_score > (heard_score * 1.20 + 0.015)


def _source_cards(source_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": chunk["id"],
            "title": chunk["title"],
            "start_sec": chunk["start_sec"],
            "end_sec": chunk["end_sec"],
            "excerpt": chunk["text"][:230] + ("…" if len(chunk["text"]) > 230 else ""),
        }
        for chunk in source_chunks
    ]


def _extract_responses_text(payload: dict[str, Any]) -> str:
    """Extract visible assistant text from the xAI Responses API response."""
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message" or item.get("role") != "assistant":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
    return "\n".join(parts).strip()


def _grok_answer(
    question: str,
    context_chunks: list[dict[str, Any]],
    context_questions: list[str] | None = None,
) -> str | None:
    """Ask xAI Grok to answer from already-heard passages only."""
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key or not context_chunks:
        return None

    model = os.getenv("XAI_MODEL", "grok-4.7").strip() or "grok-4.7"
    context = "\n\n".join(
        f"[{chunk['title']} | {chunk['start_sec']:.1f}-{chunk['end_sec']:.1f}s]\n{chunk['text']}"
        for chunk in context_chunks
    )
    recent_questions = [item.strip() for item in (context_questions or []) if item.strip()][-4:]
    previous = "\n".join(f"- {item}" for item in recent_questions) or "(none)"

    system_prompt = (
        "You are LoreFlow, a careful audiobook companion. Answer the listener's question "
        "using ONLY the supplied passages. They are the complete evidence you are allowed "
        "to use. Never use your training knowledge, outside facts, genre conventions, or "
        "events not stated in these passages. If the answer is not supported, say that the "
        "story has not revealed it in the passages heard so far. You may resolve pronouns "
        "using the listener's recent questions, but facts must come from the supplied passages. "
        "Be conversational and concise: 1-3 sentences suitable for spoken audio."
    )
    user_prompt = (
        f"RECENT QUESTIONS FROM THIS LISTENER:\n{previous}\n\n"
        f"PASSAGES HEARD SO FAR (the only allowed evidence):\n{context}\n\n"
        f"CURRENT QUESTION:\n{question}"
    )

    try:
        response = httpx.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_output_tokens": 220,
                "store": False,
            },
            timeout=45.0,
        )
        response.raise_for_status()
        answer = _extract_responses_text(response.json())
        return answer or None
    except Exception as exc:  # Keep the local presentation fallback available.
        logger.warning("Grok request failed; using local retrieval fallback: %s", exc)
        return None


def answer_question(
    question: str,
    position_sec: float,
    book: dict[str, Any],
    context_questions: list[str] | None = None,
) -> dict[str, Any]:
    question = question.strip()
    chunks = book["chunks"]
    heard = available_chunks(chunks, position_sec)

    # Prior user questions help resolve follow-ups like "why did she do that?".
    recent_questions = [item.strip() for item in (context_questions or []) if item.strip()][-4:]
    retrieval_query = " ".join(recent_questions + [question])

    if _future_only_match(retrieval_query, chunks, heard):
        return {
            "answer": "That detail appears in a passage you haven't heard yet. I'll be able to explain it when you reach that part of the story.",
            "can_answer": False,
            "spoiler_blocked": True,
            "mode": "future-passage boundary",
            "sources": [],
            "position_sec": round(position_sec, 2),
        }

    ranked = _relevant_chunks(retrieval_query, heard, top_k=4)
    if not ranked:
        return {
            "answer": "I couldn't find enough evidence for that in the passages you've heard so far. Try asking in another way, or listen to a little more of the story.",
            "can_answer": False,
            "spoiler_blocked": False,
            "mode": "timestamp-filtered retrieval",
            "sources": [],
            "position_sec": round(position_sec, 2),
        }

    # Only 'ranked' heard chunks are passed to Grok. Future text is never sent.
    live_answer = _grok_answer(question, ranked, recent_questions)
    if live_answer:
        answer = live_answer
        mode = "Grok API + heard-passage retrieval"
    else:
        excerpt = ranked[0]["text"]
        answer = f"I found this in the story you've heard: {excerpt}"
        mode = "Local retrieval fallback (add XAI_API_KEY for Grok)"

    return {
        "answer": answer,
        "can_answer": True,
        "spoiler_blocked": False,
        "mode": mode,
        "sources": _source_cards(ranked),
        "position_sec": round(position_sec, 2),
    }


def make_recap(position_sec: float, book: dict[str, Any]) -> dict[str, Any]:
    heard = available_chunks(book["chunks"], position_sec)
    if not heard:
        return {
            "recap": "Start listening and I'll build a recap from the passages you've heard.",
            "sources": [],
            "position_sec": round(position_sec, 2),
        }
    recap_text = " ".join(chunk["text"] for chunk in heard)
    sentences = re.split(r"(?<=[.!?])\s+", recap_text)
    compact = " ".join(sentences[:4])
    if len(compact) > 560:
        compact = compact[:557].rsplit(" ", 1)[0] + "…"
    return {
        "recap": compact,
        "sources": _source_cards(heard),
        "position_sec": round(position_sec, 2),
    }
