# app/test_retrieval.py

import os, sys
from collections import Counter

# 프로젝트 루트 경로 잡아주기
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from langchain_community.vectorstores import Chroma
from rag.embeddings import get_embeddings
from rag.config import CHROMA_DIR, DSM_COLLECTION_NAME


def score_criteria(doc):
    """진단기준처럼 보이는 문단을 위로 올리기 위한 간단한 스코어"""
    text = doc.page_content.lower()
    keywords = ["criteria", "a.", "b.", "symptom", "for at least", "duration"]
    return sum(1 for kw in keywords if kw in text)


def main():
    # 1) DB 열기
    embeddings = get_embeddings()
    db = Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=DSM_COLLECTION_NAME,
    )

    # 2) 사용자 증상 (여기만 바꿔가며 테스트하면 됨)
    user_symptom = "obsessive thoughts, compulsive behaviors, checking behaviors, anxiety, catastrophic thinking, occupational impairment (work delays), physical fatigue"

    # 3) 1차 검색: 증상과 비슷한 chunk 몇 개 뽑기
    hits = db.similarity_search(user_symptom, k=12)

    # 4) 검색된 chunk들에서 diagnosis 메타데이터만 모아서 투표
    diags = [h.metadata.get("diagnosis", "Unknown") for h in hits]
    counts = Counter(diags)

    # Unknown은 우선순위에서 빼고 싶으니까 제거
    if "Unknown" in counts:
        del counts["Unknown"]

    # 가능성 높은 병명 3개 뽑기
    top_diags = [d for d, _ in counts.most_common(3)]

    print("=== 증상:", user_symptom)
    print("=== 후보 병명 TOP3 ===")
    if not top_diags:
        print("병명 후보를 찾지 못했어요. 메타데이터(Page→Diagnosis) 범위를 다시 확인하세요.")
        return

    for i, d in enumerate(top_diags, 1):
        print(f"{i}. {d}")

    # 5) 각 병명마다 '진단 기준'에 가까운 문단 뽑기
    print("\n=== 병명별 진단 기준 후보 ===")
    for diag in top_diags:
        # 병명을 필터로 고정하고, 쿼리에는 'diagnostic criteria'를 꼭 넣는다
        raw_hits = db.similarity_search(
            f"diagnostic criteria for {diag}",
            k=10,
            filter={"diagnosis": diag}
        )

        # 기준처럼 보이는 순서로 정렬
        ranked = sorted(raw_hits, key=score_criteria, reverse=True)
        top_chunks = ranked[:3]

        print(f"\n--- {diag} ---")
        if not top_chunks:
            print("진단 기준을 찾지 못했습니다.")
            continue

        for idx, chunk in enumerate(top_chunks, 1):
            print(f"\n[{idx}]")
            print(chunk.page_content[:400])  # 너무 길면 앞부분만
            # LLM에 보낼 때는 chunk.page_content 전체를 그대로 붙이면 됨

    # 여기까지가 "RAG로 3개 병명 + 각 병명 기준 문단" 뽑는 파트.
    # 이 출력들을 LLM에 넣어서 "이 3개 중에 뭐가 제일 맞는지 사용자한테 질문해" 같은 프롬프트 만들면 됨.


if __name__ == "__main__":
    main()
