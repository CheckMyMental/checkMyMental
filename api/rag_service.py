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

# 임베딩은 서버 시작 시 한 번만
_embeddings = get_embeddings()

# DSM 기준 컬렉션
_dsm_db = Chroma(
    embedding_function=_embeddings,
    persist_directory=CHROMA_DIR,
    collection_name=DSM_COLLECTION_NAME,
)

# 치료 컬렉션
_treatment_db = Chroma(
    embedding_function=_embeddings,
    persist_directory=CHROMA_DIR,
    collection_name=TREATMENT_COLLECTION_NAME,
)


def retrieve_candidates(symptom_text: str, top_k: int = 12, diag_top_n: int = 3) -> Dict[str, Any]:
    """
    1) 사용자가 말한 증상으로 DSM 컬렉션에서 문단 k개 검색
    2) 문단들의 metadata.disorder 빈도수로 상위 n개 진단 후보 뽑기
    3) 각 진단에 대해 criteria 문단(가장 긴 것) 하나씩 붙여서 반환
    """
    # 1) 증상 기반 검색
    hits = _dsm_db.similarity_search(symptom_text, k=top_k)

    # 2) disorder 투표
    diags = [
        h.metadata.get("disorder")
        for h in hits
        if h.metadata.get("disorder")
    ]
    counts = Counter(diags)
    top_diags = [d for d, _ in counts.most_common(diag_top_n)]

    result: Dict[str, Any] = {
        "input_symptom": symptom_text,
        "diagnosis_candidates": top_diags,
        "by_diagnosis": {},
        "raw_hits": [
            {"text": h.page_content, "metadata": h.metadata}
            for h in hits
        ],
    }

    # 3) 각 진단 후보에 대해 기준 문단 다시 가져오기
    for diag in top_diags:
        raw = _dsm_db.similarity_search(
            "diagnostic criteria",
            k=200,
            filter={"disorder": diag},
        )

        # criteria 섹션만
        criteria_docs = [
            r for r in raw
            if r.metadata.get("section") == "criteria"
        ]

        if criteria_docs:
            # 가장 긴 문단 1개만
            longest = max(
                criteria_docs,
                key=lambda d: len(d.page_content or "")
            )
            result["by_diagnosis"][diag] = [
                {
                    "text": longest.page_content,
                    "metadata": longest.metadata,
                }
            ]
        else:
            result["by_diagnosis"][diag] = []

    return result


def _metadata_matches_disorder(meta_disorder: Optional[str], diagnosis: str) -> bool:
    """
    treatment 컬렉션 메타데이터는 전부 문자열이라고 가정.
    두 개 병명이 "A / B"로 묶여있을 수 있으니 부분 포함으로만 판정.
    """
    if not meta_disorder or not diagnosis:
        return False
    return diagnosis.lower() in meta_disorder.lower()


def retrieve_solution(diagnosis: str, symptom_text: Optional[str] = None) -> Dict[str, Any]:
    """
    확정된 진단명 + (선택) 증상 설명을 넣으면
    treatment 컬렉션에서 관련 치료 문단을 찾아서 주는 함수.
    """
    # 쿼리 생성
    if symptom_text:
        query = f"{diagnosis} {symptom_text} treatment"
    else:
        query = f"{diagnosis} treatment"

    # 치료 컬렉션에서 우선 여러 개 가져온다
    hits = _treatment_db.similarity_search(query, k=15)

    matched: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []

    for h in hits:
        meta_dis = h.metadata.get("disorder")
        item = {
            "text": h.page_content,
            "metadata": h.metadata,
        }
        if _metadata_matches_disorder(meta_dis, diagnosis):
            matched.append(item)
        else:
            others.append(item)

    # 정확히(또는 부분 포함으로) 매칭된 것들이 먼저 오도록
    ordered = matched + others

    return {
        "diagnosis": diagnosis,
        "query": query,
        "solutions": ordered[:5],  # 너무 많으면 앞에서 5개만
    }
