# api/rag_service.py
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from collections import Counter
from langchain_community.vectorstores import Chroma
from rag.embeddings import get_embeddings
from rag.config import CHROMA_DIR, DSM_COLLECTION_NAME

# 서버 시작 시 한 번만 로드
_embeddings = get_embeddings()
_db = Chroma(
    embedding_function=_embeddings,
    persist_directory=CHROMA_DIR,
    collection_name=DSM_COLLECTION_NAME,
)


def retrieve_candidates(symptom_text: str, top_k: int = 12, diag_top_n: int = 3):
    """
    1) 증상으로 문단 k개 검색
    2) 그 문단들에서 가장 많이 등장한 'disorder' 상위 n개 뽑기
    3) 각 disorder마다 section == 'criteria' 인 문단들을 가져오되, 가장 긴 것 1개만 반환
    """
    # 1) 증상 기반 문단 검색
    hits = _db.similarity_search(symptom_text, k=top_k)

    # 2) disorder 투표
    diags = [
        h.metadata.get("disorder")
        for h in hits
        if h.metadata.get("disorder")
    ]
    counts = Counter(diags)
    top_diags = [d for d, _ in counts.most_common(diag_top_n)]

    result = {
        "input_symptom": symptom_text,
        "diagnosis_candidates": top_diags,
        "by_diagnosis": {},
        "raw_hits": [
            {"text": h.page_content, "metadata": h.metadata}
            for h in hits
        ],
    }

    # 3) 각 disorder에 대해 기준문단 가져오기
    for diag in top_diags:
        raw = _db.similarity_search(
            "diagnostic criteria",
            k=200,
            filter={"disorder": diag},
        )

        # section == "criteria" 만 뽑기
        criteria_docs = [
            r for r in raw
            if r.metadata.get("section") == "criteria"
        ]

        # 🔥 여기서 가장 긴 기준 문단 하나만 남긴다
        if criteria_docs:
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


def retrieve_solution(diagnosis: str):
    """
    확정 질환명의 설명/관련 문단을 다시 검색
    """
    hits = _db.similarity_search(
        f"information about {diagnosis}",
        k=5,
        filter={"disorder": diagnosis},
    )
    return {
        "diagnosis": diagnosis,
        "evidence": [
            {"text": h.page_content, "metadata": h.metadata} for h in hits
        ],
    }
