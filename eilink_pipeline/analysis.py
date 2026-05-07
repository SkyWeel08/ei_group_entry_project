from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


def keyword_extraction_per_report(reports_df: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if reports_df.empty:
        return pd.DataFrame(columns=["report_id", "pdf_name", "keyword_rank", "keyword", "tfidf_score"])

    corpus = (
        reports_df.get("summary_activities_24h", pd.Series("", index=reports_df.index)).fillna("")
        + " "
        + reports_df.get("summary_planned_24h", pd.Series("", index=reports_df.index)).fillna("")
        + " "
        + reports_df.get("operations_section_raw", pd.Series("", index=reports_df.index)).fillna("")
        + " "
        + reports_df.get("equipment_failure_section_raw", pd.Series("", index=reports_df.index)).fillna("")
    )
    if not corpus.str.strip().any():
        return pd.DataFrame(columns=["report_id", "pdf_name", "keyword_rank", "keyword", "tfidf_score"])

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=12000,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_/-]{2,}\b",
    )
    tfidf = vectorizer.fit_transform(corpus.values)
    terms = np.array(vectorizer.get_feature_names_out())
    rows = []
    for row_pos, report_id in enumerate(reports_df["report_id"].tolist()):
        vec = tfidf[row_pos].toarray().ravel()
        top_idx = vec.argsort()[-top_n:][::-1]
        for rank, term_idx in enumerate(top_idx, start=1):
            score = float(vec[term_idx])
            if score <= 0:
                continue
            rows.append(
                {
                    "report_id": report_id,
                    "pdf_name": reports_df.loc[row_pos, "pdf_name"],
                    "keyword_rank": rank,
                    "keyword": terms[term_idx],
                    "tfidf_score": score,
                }
            )
    return pd.DataFrame(rows)
