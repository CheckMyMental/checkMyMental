# api/rag_service.py

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from collections import Counter
from typing import Optional, List, Dict, Any

from langchain_community.vectorstores import Chroma
from rag.embeddings import get_embeddings
from rag.config import (
    CHROMA_DIR,
    DSM_COLLECTION_NAME,
    TREATMENT_COLLECTION_NAME,
)

# 🔥 추가: DSM → Treatment Category 매핑 함수
from rag.disorder_classifier import classify_disorder


# -----------------------------
# Embedder & DB 초기화
# -----------------------------
_embeddings = get_embeddings()

_dsm_db = Chroma(
    embedding_function=_embeddings,
    persist_directory=CHROMA_DIR,
    collection_name=DSM_COLLECTION_NAME,
)

_treatment_db = Chroma(
    embedding_function=_embeddings,
    persist_directory=CHROMA_DIR,
    collection_name=TREATMENT_COLLECTION_NAME,
)


# -----------------------------
# DSM Hypothesis Search
# -----------------------------
def retrieve_candidates(symptom_text: str, top_k: int = 12, diag_top_n: int = 3) -> Dict[str, Any]:

    hits = _dsm_db.similarity_search(symptom_text, k=top_k)

    diags = [h.metadata.get("disorder") for h in hits if h.metadata.get("disorder")]
    counts = Counter(diags)
    top_diags = [d for d, _ in counts.most_common(diag_top_n)]

    result: Dict[str, Any] = {
        "input_symptom": symptom_text,
        "diagnosis_candidates": top_diags,
        "by_diagnosis": {},
        "raw_hits": [{"text": h.page_content, "metadata": h.metadata} for h in hits],
    }

    for diag in top_diags:
        raw = _dsm_db.similarity_search(
            "diagnostic criteria",
            k=200,
            filter={"disorder": diag},
        )

        criteria_docs = [r for r in raw if r.metadata.get("section") == "criteria"]

        if criteria_docs:
            longest = max(criteria_docs, key=lambda d: len(d.page_content or ""))
            result["by_diagnosis"][diag] = [{
                "text": longest.page_content,
                "metadata": longest.metadata,
            }]
        else:
            result["by_diagnosis"][diag] = []

    return result



# -----------------------------
# 내부 매칭 함수
# -----------------------------
def _metadata_matches_disorder(meta_disorder: Optional[str], category: str) -> bool:
    if not meta_disorder or not category:
        return False
    return category.lower() in meta_disorder.lower()



# -----------------------------
# Treatment Retrieval (FIXED)
# -----------------------------
def retrieve_solution(diagnosis: str, symptom_text: Optional[str] = None) -> Dict[str, Any]:

    # 🔥 1) DSM 병명 → 치료 카테고리 변환
    treatment_category = classify_disorder(diagnosis)

    if treatment_category is None:
        return {
            "diagnosis": diagnosis,
            "treatment_category": None,
            "solutions": [],
            "message": "해당 진단의 치료 문서가 없습니다."
        }

    # 🔥 2) Query 생성
    if symptom_text:
        query = f"{treatment_category} {symptom_text} treatment"
    else:
        query = f"{treatment_category} treatment"

    # 🔥 3) Treatment DB에서 검색
    hits = _treatment_db.similarity_search(query, k=15)

    matched = []
    others = []

    for h in hits:
        meta_dis = h.metadata.get("disorder")
        item = {
            "text": h.page_content,
            "metadata": h.metadata,
        }

        # 🔥 4) metadata["disorder"]가 treatment_category와 맞는지 확인
        if _metadata_matches_disorder(meta_dis, treatment_category):
            matched.append(item)
        else:
            others.append(item)

    ordered = matched + others

    return {
        "diagnosis": diagnosis,
        "treatment_category": treatment_category,
        "query": query,
        "solutions": ordered[:5],
    }
