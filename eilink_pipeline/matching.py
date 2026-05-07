from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "was",
    "were",
    "while",
    "into",
    "over",
    "than",
    "then",
    "have",
    "has",
    "had",
    "all",
    "not",
    "out",
    "per",
    "day",
    "hrs",
    "hour",
    "hours",
    "well",
    "hole",
    "drilling",
    "report",
    "section",
}


def normalize_well_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", "", value.strip().upper().replace("_", "/"))


def tokenize_for_overlap(text: object) -> set[str]:
    if not isinstance(text, str):
        return set()
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_/.-]+", text.lower())
    return {token for token in tokens if token not in STOPWORDS and len(token) > 2}


def tokenize_for_bm25(text: object) -> list[str]:
    return sorted(tokenize_for_overlap(text))


def _minmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    min_val = float(values.min())
    max_val = float(values.max())
    if max_val == min_val:
        return np.zeros_like(values, dtype=float)
    return (values - min_val) / (max_val - min_val)


def _safe_tfidf_scores(event_text: str, candidate_texts: list[str], **kwargs: object) -> np.ndarray:
    try:
        stop_words = "english" if kwargs.get("analyzer", "word") == "word" else None
        vectorizer = TfidfVectorizer(stop_words=stop_words, **kwargs)
        matrix = vectorizer.fit_transform([event_text] + candidate_texts)
        return cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    except ValueError:
        return np.zeros(len(candidate_texts), dtype=float)


def score_candidates(event_text: str, candidate_texts: list[str]) -> dict[str, np.ndarray]:
    word_scores = _safe_tfidf_scores(event_text, candidate_texts, ngram_range=(1, 2))
    char_scores = _safe_tfidf_scores(event_text, candidate_texts, analyzer="char_wb", ngram_range=(3, 5))
    fuzzy_scores = np.array([fuzz.token_set_ratio(event_text, text) / 100.0 for text in candidate_texts], dtype=float)

    event_tokens = tokenize_for_overlap(event_text)
    overlap_scores = []
    for text in candidate_texts:
        candidate_tokens = tokenize_for_overlap(text)
        denom = len(event_tokens | candidate_tokens)
        overlap_scores.append(len(event_tokens & candidate_tokens) / denom if denom else 0.0)
    overlap = np.array(overlap_scores, dtype=float)

    tokenized = [tokenize_for_bm25(text) for text in candidate_texts]
    bm25_raw = np.zeros(len(candidate_texts), dtype=float)
    if any(tokenized) and event_tokens:
        bm25 = BM25Okapi(tokenized)
        bm25_raw = np.array(bm25.get_scores(tokenize_for_bm25(event_text)), dtype=float)
    bm25_scores = _minmax(bm25_raw)

    ensemble = 0.35 * word_scores + 0.25 * char_scores + 0.2 * fuzzy_scores + 0.1 * bm25_scores + 0.1 * overlap
    return {
        "score_tfidf_word": word_scores,
        "score_tfidf_char": char_scores,
        "score_fuzzy": fuzzy_scores,
        "score_bm25": bm25_scores,
        "score_keyword_overlap": overlap,
        "ensemble_score": ensemble,
    }


def match_nds_events(nds_df: pd.DataFrame, reports_df: pd.DataFrame, operations_df: pd.DataFrame, *, top_n: int = 5) -> pd.DataFrame:
    if operations_df.empty:
        return pd.DataFrame()

    op_join = operations_df.merge(
        reports_df[["report_id", "pdf_name", "wellbore_id"]],
        on="report_id",
        how="left",
    )
    op_join["wellbore_norm"] = op_join["wellbore_id"].apply(normalize_well_name)
    op_join["operation_text"] = (
        op_join["main_activity"].fillna("")
        + " "
        + op_join["sub_activity"].fillna("")
        + " "
        + op_join["remark"].fillna("")
    ).str.strip()

    rows = []
    for event_idx, event_row in nds_df.iterrows():
        well = normalize_well_name(event_row.get("Well"))
        event_text = str(event_row.get("Event", "")).strip()
        candidates = op_join[op_join["wellbore_norm"] == well].copy()
        if candidates.empty:
            rows.append(
                {
                    "event_id": int(event_idx + 1),
                    "well": well,
                    "event_text": event_text,
                    "matched": False,
                    "reason": "No candidate operations found for this well.",
                    "matched_pdf": None,
                    "matched_operation_id": None,
                    "matched_excerpt": None,
                    "top_candidates_json": "[]",
                    "score_tfidf_word": 0.0,
                    "score_tfidf_char": 0.0,
                    "score_fuzzy": 0.0,
                    "score_bm25": 0.0,
                    "score_keyword_overlap": 0.0,
                    "ensemble_score": 0.0,
                }
            )
            continue

        candidate_texts = candidates["operation_text"].fillna("").tolist()
        scores = score_candidates(event_text, candidate_texts)
        best_idx = int(np.argmax(scores["ensemble_score"]))
        best = candidates.iloc[best_idx]
        top_indices = scores["ensemble_score"].argsort()[-top_n:][::-1]
        top_candidates = []
        for rank, candidate_idx in enumerate(top_indices, start=1):
            cand = candidates.iloc[int(candidate_idx)]
            top_candidates.append(
                {
                    "rank": rank,
                    "operation_id": int(cand["operation_id"]),
                    "pdf_name": cand["pdf_name"],
                    "excerpt": cand["remark"],
                    "ensemble_score": float(scores["ensemble_score"][candidate_idx]),
                    "score_tfidf_word": float(scores["score_tfidf_word"][candidate_idx]),
                    "score_tfidf_char": float(scores["score_tfidf_char"][candidate_idx]),
                    "score_fuzzy": float(scores["score_fuzzy"][candidate_idx]),
                    "score_bm25": float(scores["score_bm25"][candidate_idx]),
                    "score_keyword_overlap": float(scores["score_keyword_overlap"][candidate_idx]),
                }
            )

        rows.append(
            {
                "event_id": int(event_idx + 1),
                "well": well,
                "event_text": event_text,
                "matched": True,
                "reason": "Matched by ensemble benchmark (word TF-IDF + char TF-IDF + fuzzy + BM25 + keyword overlap).",
                "matched_pdf": best["pdf_name"],
                "matched_operation_id": int(best["operation_id"]),
                "matched_excerpt": best["remark"],
                "top_candidates_json": json.dumps(top_candidates, ensure_ascii=False),
                "score_tfidf_word": float(scores["score_tfidf_word"][best_idx]),
                "score_tfidf_char": float(scores["score_tfidf_char"][best_idx]),
                "score_fuzzy": float(scores["score_fuzzy"][best_idx]),
                "score_bm25": float(scores["score_bm25"][best_idx]),
                "score_keyword_overlap": float(scores["score_keyword_overlap"][best_idx]),
                "ensemble_score": float(scores["ensemble_score"][best_idx]),
            }
        )
    return pd.DataFrame(rows)
