# rag/build_dsm_db.py

import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from langchain_community.vectorstores import Chroma
from langchain.schema import Document  # langchain>=0.1 기준
from rag.config import DSM_PDF_PATH, CHROMA_DIR, DSM_COLLECTION_NAME
from rag.embeddings import get_embeddings


# F코드 같은 진단 코드: DSM-5-TR에서 Diagnostic Criteria 오른쪽에 붙어있는 애
ICD_PATTERN = re.compile(r"^F\d{2}(\.\d+)?$")

# A. / B. / C. 같은 진단 기준 줄
CRITERIA_PATTERN = re.compile(r"^[A-Z]\.\s")

# 1. / 2. 같은 서브 기준 줄
SUBCRITERIA_PATTERN = re.compile(r"^\d+\.\s")


def looks_like_disorder_title(text: str) -> bool:
    """
    오른쪽 열에 있는 한 줄짜리 병명 후보가 텍스트 모양만 봐도 병명처럼 보이는지 확인.
    """
    text = text.strip()
    if not text:
        return False

    # 너무 길면 본문일 확률 ↑
    if len(text) > 150:
        return False

    # 문장부호 많은 건 일단 제외
    if "." in text and "..." not in text:
        # 병명에 . 이 잘 안 들어가니까 대충 컷
        return False

    # 단어 수 1~8 사이면 병명이거나 소제목일 확률이 높다
    words = text.split()
    if not (1 <= len(words) <= 8):
        return False

    # 대문자로 시작하는 단어 비율
    cap_ratio = sum(1 for w in words if w[0].isupper()) / len(words)
    if cap_ratio < 0.6:
        return False

    return True


def group_words_to_lines(words, y_tolerance=3.0):
    """
    pdfplumber가 단어 단위로 주는 걸 y값 비슷한 것끼리 묶어서 '줄'로 만든다.
    반환: [ { "text": "...", "x0": float, "x1": float, "top": float, "words": [...] }, ... ]
    """
    lines = []
    current_line = []
    current_top = None

    for w in words:
        top = w["top"]
        if current_top is None:
            # 첫 단어
            current_top = top
            current_line.append(w)
            continue

        if abs(top - current_top) <= y_tolerance:
            # 같은 줄로 본다
            current_line.append(w)
        else:
            # 줄 하나 끝
            line_text = " ".join(x["text"] for x in current_line)
            x0 = min(x["x0"] for x in current_line)
            x1 = max(x["x1"] for x in current_line)
            lines.append({
                "text": line_text,
                "x0": x0,
                "x1": x1,
                "top": current_top,
                "words": current_line,
            })
            # 새 줄 시작
            current_line = [w]
            current_top = top

    if current_line:
        line_text = " ".join(x["text"] for x in current_line)
        x0 = min(x["x0"] for x in current_line)
        x1 = max(x["x1"] for x in current_line)
        lines.append({
            "text": line_text,
            "x0": x0,
            "x1": x1,
            "top": current_top,
            "words": current_line,
        })

    return lines


def main():
    print("[1] PDF 읽는 중...")

    docs: list[Document] = []

    # 상태 변수
    candidate_disorder = None   # 오른쪽에서 한 줄짜리로 본 병명 후보
    current_disorder = None     # 실제로 확정된 병명
    in_criteria_section = False # A. B. 나오는 진단 기준 박스 안인지

    with pdfplumber.open(DSM_PDF_PATH) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            width = page.width
            words = page.extract_words(use_text_flow=True)

            if not words:
                continue

            lines = group_words_to_lines(words)

            for line in lines:
                text = line["text"].strip()
                x0 = line["x0"]
                x1 = line["x1"]

                # 1) 오른쪽에 있는 한 줄짜리 → 병명 후보
                #    (병명이 길어서 좀 왼쪽으로 빠질 수 있으니 x1 기준도 같이 본다)
                right_aligned_like = (x1 > width * 0.85) or (x0 > width * 0.6 and len(text) < 150)
                if right_aligned_like and looks_like_disorder_title(text):
                    candidate_disorder = text
                    # 병명 후보일 뿐 아직 확정은 아님
                    continue

                # 2) Diagnostic Criteria + F코드가 같은 줄에 있는 경우 → 병명 확정
                #    왼쪽에 Diagnostic Criteria, 오른쪽에 F코드
                if "Diagnostic Criteria" in text:
                    # 줄 안에서 F코드가 있는지 먼저 확인
                    fcode_word = None
                    for w in line["words"]:
                        if ICD_PATTERN.match(w["text"].strip()):
                            fcode_word = w
                            break

                    if fcode_word is not None:
                        # 왼쪽은 Diagnostic Criteria, 오른쪽은 F코드 → 이 줄이 진단박스 헤더
                        if candidate_disorder:
                            current_disorder = candidate_disorder
                        in_criteria_section = True
                        # 이 줄 자체는 보통 저장 안 해도 되는데,
                        # 추후 디버깅용으로 넣고 싶으면 아래 주석 해제
                        # docs.append(Document(page_content=text, metadata={...}))
                        continue
                    else:
                        # Diagnostic Criteria만 있고 F코드는 없으면 일단 기준 시작으로만 본다
                        if candidate_disorder:
                            current_disorder = candidate_disorder
                        in_criteria_section = True
                        continue

                # 3) A. / B. / C. 시작 → 이건 진단기준 줄
                if CRITERIA_PATTERN.match(text) or SUBCRITERIA_PATTERN.match(text):
                    if current_disorder:
                        docs.append(Document(
                            page_content=text,
                            metadata={
                                "page": page_idx,
                                "disorder": current_disorder,
                                "section": "criteria",
                                "is_criteria": True,
                            }
                        ))
                    # 이 줄은 저장했으니 다음 줄로
                    continue

                # 4) 그 외의 줄들
                if current_disorder:
                    # 지금 어떤 병명 안에 있는 본문/설명
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "page": page_idx,
                            "disorder": current_disorder,
                            "section": "description",
                            "is_criteria": False,
                        }
                    ))
                else:
                    # 병명 밖에 있는 잡텍스트는 보통 RAG에 안 넣어도 되는데
                    # 일단은 넣지 않고 스킵
                    continue

    print(f" → 총 {len(docs)}개 줄 단위 chunk")

    print("[2] 임베딩 + Chroma 저장 중...")
    embeddings = get_embeddings()

    db = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=DSM_COLLECTION_NAME,
    )
    db.persist()

    print("[완료] DSM Chroma DB 생성됨:", CHROMA_DIR)


if __name__ == "__main__":
    main()
