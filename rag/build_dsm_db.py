# rag/build_dsm_db.py

import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

from rag.config import DSM_PDF_PATH, CHROMA_DIR, DSM_COLLECTION_NAME
from rag.embeddings import get_embeddings

ICD_PATTERN = re.compile(r"^F\d{2}(\.\d+)?$")
CRITERIA_PATTERN = re.compile(r"^[A-Z]\.\s")
SUBCRITERIA_PATTERN = re.compile(r"^\d+\.\s")


def looks_like_disorder_title(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if len(text) > 150:
        return False
    words = text.split()
    if not (1 <= len(words) <= 8):
        return False
    cap_ratio = sum(1 for w in words if w[0].isupper()) / len(words)
    if cap_ratio < 0.6:
        return False
    return True


def group_words_to_lines(words, y_tolerance=3.0):
    lines = []
    current_line = []
    current_top = None

    for w in words:
        top = w["top"]
        if current_top is None:
            current_top = top
            current_line.append(w)
            continue

        if abs(top - current_top) <= y_tolerance:
            current_line.append(w)
        else:
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
    embeddings = get_embeddings()

    candidate_disorder = None
    current_disorder = None
    in_criteria_section = False

    criteria_buffer: list[str] = []
    criteria_indent: float = 0.0   # A. 줄의 들여쓰기 기억
    description_buffer: list[str] = []
    DESCRIPTION_MAX_LEN = 700

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

                # 1) 오른쪽 한 줄짜리 → 병명 후보
                right_like = (x1 > width * 0.85) or (x0 > width * 0.6 and len(text) < 150)
                if right_like and looks_like_disorder_title(text):
                    # 이전 설명 flush
                    if current_disorder and description_buffer:
                        big_text = "\n".join(description_buffer)
                        docs.append(Document(
                            page_content=big_text,
                            metadata={
                                "page": page_idx,
                                "disorder": current_disorder,
                                "section": "description",
                                "is_criteria": False,
                            }
                        ))
                        description_buffer = []
                    candidate_disorder = text
                    criteria_buffer = []
                    in_criteria_section = False
                    continue

                # 2) Diagnostic Criteria 줄 → 병명 확정 + criteria 시작
                if "Diagnostic Criteria" in text:
                    # F코드 있는지 확인 (지금은 안 써도 됨)
                    for w in line["words"]:
                        if ICD_PATTERN.match(w["text"].strip()):
                            break

                    if candidate_disorder:
                        current_disorder = candidate_disorder
                        candidate_disorder = None

                    in_criteria_section = True
                    criteria_buffer = []
                    criteria_indent = 0.0
                    continue

                # 3) criteria 구간 안에서
                is_crit_head = bool(CRITERIA_PATTERN.match(text) or SUBCRITERIA_PATTERN.match(text))

                if in_criteria_section and current_disorder:
                    if is_crit_head:
                        # 새로운 A./B./1./2. 시작
                        criteria_buffer.append(text)
                        # 이 줄의 들여쓰기 기억
                        criteria_indent = x0
                        continue
                    else:
                        # 패턴은 아니지만 아직 criteria 구간인 줄
                        # → 들여쓰기가 기준줄보다 조금 더 들어가 있으면 이어지는 줄로 본다
                        # 여유값 3~5 정도
                        if criteria_buffer and x0 >= criteria_indent - 2:
                            # 같은 항목의 이어지는 줄
                            criteria_buffer.append(text)
                            continue
                        else:
                            # 이제 진짜 기준 끝난 것 → 지금까지 쌓인 기준 저장
                            criteria_text = "\n".join(criteria_buffer)
                            docs.append(Document(
                                page_content=criteria_text,
                                metadata={
                                    "page": page_idx,
                                    "disorder": current_disorder,
                                    "section": "criteria",
                                    "is_criteria": True,
                                }
                            ))
                            criteria_buffer = []
                            in_criteria_section = False
                            # 그리고 이 줄은 설명부로 내려가서 처리한다

                # 4) 설명부로 저장
                if current_disorder:
                    description_buffer.append(text)
                    total_len = sum(len(t) for t in description_buffer)
                    if total_len >= DESCRIPTION_MAX_LEN:
                        big_text = "\n".join(description_buffer)
                        docs.append(Document(
                            page_content=big_text,
                            metadata={
                                "page": page_idx,
                                "disorder": current_disorder,
                                "section": "description",
                                "is_criteria": False,
                            }
                        ))
                        description_buffer = []
                else:
                    continue

            # 페이지 끝: criteria 남아 있으면 저장
            if in_criteria_section and criteria_buffer and current_disorder:
                criteria_text = "\n".join(criteria_buffer)
                docs.append(Document(
                    page_content=criteria_text,
                    metadata={
                        "page": page_idx,
                        "disorder": current_disorder,
                        "section": "criteria",
                        "is_criteria": True,
                    }
                ))
                criteria_buffer = []
                in_criteria_section = False

            # 페이지 끝: 설명 남아 있으면 저장
            if current_disorder and description_buffer:
                big_text = "\n".join(description_buffer)
                docs.append(Document(
                    page_content=big_text,
                    metadata={
                        "page": page_idx,
                        "disorder": current_disorder,
                        "section": "description",
                        "is_criteria": False,
                    }
                ))
                description_buffer = []

    print(f" → 총 {len(docs)}개 chunk 생성")

    print("[2] 임베딩 + Chroma 저장 중...")
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
