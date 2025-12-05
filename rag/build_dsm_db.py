# rag/build_dsm_db.py

import os
import sys
import re
import difflib

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

from rag.embeddings import get_embeddings
from rag.config import DSM_PDF_PATH, CHROMA_DIR, DSM_COLLECTION_NAME, KNOWN_DISORDERS

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


# ----------------------
# KNOWN_DISORDERS 매칭 유틸
# ----------------------


def normalize_title(text: str) -> str:
    """
    DSM 병명 비교용 간단 정규화:
    - 양쪽 공백 제거
    - 괄호 안 내용 삭제: (Intellectual Disability), (type 1) 등
    - 여러 공백 -> 한 칸
    - 소문자화
    """
    t = text.strip()
    t = re.sub(r"\s*\([^)]*\)", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.lower()


_NORMALIZED_KNOWN = {
    normalize_title(name): name for name in KNOWN_DISORDERS
}


def match_disorder_title(raw_title: str, threshold: float = 0.82):
    """
    PDF에서 뽑은 병명 후보(raw_title)를 KNOWN_DISORDERS와 fuzzy 매칭해서
    threshold 이상이면 canonical 이름을 리턴, 아니면 None.
    """
    norm = normalize_title(raw_title)
    best_name = None
    best_score = 0.0

    for norm_known, canon in _NORMALIZED_KNOWN.items():
        score = difflib.SequenceMatcher(None, norm, norm_known).ratio()
        if score > best_score:
            best_score = score
            best_name = canon

    if best_name and best_score >= threshold:
        return best_name
    return None


# ----------------------
# 섹션 헤더 감지 (Diagnostic Features, Prevalence 등)
# ----------------------


def looks_like_section_header(text: str, x0: float, page_width: float) -> bool:
    """
    Diagnostic Features / Prevalence / Development and Course 등 DSM 섹션 제목 패턴.

    조건:
    - 빈 줄 X
    - 너무 길지 않음 (예: 80자 이하 정도)
    - 끝이 ':' 인 것 제외 (Specify current severity: 같은 문장 제거)
    - 단어 중 상당수가 앞글자 대문자 (Title Case / ALL CAPS)
    - 페이지의 꽤 왼쪽에서 시작 (박스 안 텍스트보다 더 왼쪽)
    """
    t = text.strip()
    if not t:
        return False
    if len(t) > 80:
        return False
    if t.endswith(":"):
        # "Specify current severity:" 같은 건 헤더로 보지 않는다
        return False

    words = t.split()
    # 단어 수는 1개인 경우도 허용 (Prevalence 같은 케이스)
    cap_words = 0
    for w in words:
        if not w:
            continue
        ch = w[0]
        if ch.isupper():
            cap_words += 1

    if cap_words / len(words) < 0.6:
        return False

    # 섹션 헤더는 보통 페이지 왼쪽에 붙어 있음
    if x0 > page_width * 0.3:
        return False

    return True


def main():
    print("[1] PDF 읽는 중...")

    docs: list[Document] = []
    embeddings = get_embeddings()

    candidate_disorder = None          # Diagnostic Criteria 나오기 전까지의 '후보' 병명
    current_disorder = None            # 실제 메타데이터에 들어갈 병명(raw)
    current_canonical_disorder = None  # KNOWN_DISORDERS 기준 canonical 이름
    in_criteria_section = False

    criteria_buffer: list[str] = []
    description_buffer: list[str] = []
    DESCRIPTION_MAX_LEN = 700

    START_PAGE = 131
    END_PAGE = 1067

    with pdfplumber.open(DSM_PDF_PATH) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):

            if page_idx < START_PAGE or page_idx > END_PAGE:
                continue

            width = page.width
            words = page.extract_words(use_text_flow=True)
            if not words:
                continue

            lines = group_words_to_lines(words)

            for line in lines:
                text = line["text"].strip()
                x0 = line["x0"]
                x1 = line["x1"]

                # 0) criteria 박스 안에서 섹션 헤더를 만나면 → 박스 종료
                if in_criteria_section and current_disorder:
                    if looks_like_section_header(text, x0, width):
                        # 지금까지 쌓인 criteria 박스 전체를 하나의 청크로 저장
                        if criteria_buffer:
                            criteria_text = "\n".join(criteria_buffer)
                            docs.append(Document(
                                page_content=criteria_text,
                                metadata={
                                    "page": page_idx,
                                    "disorder": current_disorder,
                                    "canonical_disorder": current_canonical_disorder,
                                    "section": "criteria",
                                    "is_criteria": True,
                                }
                            ))
                            criteria_buffer = []
                        in_criteria_section = False
                        # 이 줄(섹션 헤더)은 description에도 넣지 않고 건너뜀
                        continue
                    else:
                        # 아직 박스 안 → 줄을 계속 모은다
                        criteria_buffer.append(text)
                        continue

                # 1) 오른쪽 한 줄짜리 → 병명 '후보'
                right_like = (x1 > width * 0.85) or (x0 > width * 0.6 and len(text) < 150)
                if right_like and looks_like_disorder_title(text):
                    # 이전 설명 flush (현재 확정된 current_disorder 기준)
                    if current_disorder and description_buffer:
                        big_text = "\n".join(description_buffer)
                        docs.append(Document(
                            page_content=big_text,
                            metadata={
                                "page": page_idx,
                                "disorder": current_disorder,
                                "canonical_disorder": current_canonical_disorder,
                                "section": "description",
                                "is_criteria": False,
                            }
                        ))
                        description_buffer = []

                    candidate_disorder = text
                    # criteria 모드는 아니고, 일단 후보만 들고 있다가
                    # Diagnostic Criteria 줄에서 KNOWN_DISORDERS로 검증 후 승격
                    continue

                # 2) Diagnostic Criteria 줄 → 병명 확정 + criteria 시작
                if "Diagnostic Criteria" in text:
                    # 필요하면 여기서 ICD 코드도 추출 가능
                    for w in line["words"]:
                        if ICD_PATTERN.match(w["text"].strip()):
                            break

                    if candidate_disorder:
                        matched = match_disorder_title(candidate_disorder)
                        if matched:
                            current_disorder = candidate_disorder
                            current_canonical_disorder = matched
                        else:
                            print(
                                f"[WARN] page {page_idx}: "
                                f"candidate_disorder '{candidate_disorder}' "
                                f"did not match KNOWN_DISORDERS."
                            )
                        candidate_disorder = None

                    in_criteria_section = True
                    criteria_buffer = []   # 박스 전체를 여기다 쌓는다
                    continue

                # 3) criteria 모드가 아닌데 섹션 헤더가 나오면?
                #    (Diagnostic Features, Prevalence 등) → description 앞의 제목이라면 굳이 저장 안 해도 됨
                if looks_like_section_header(text, x0, width):
                    # 현재 구현에서는 제목 줄은 그냥 스킵
                    continue

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
                                "canonical_disorder": current_canonical_disorder,
                                "section": "description",
                                "is_criteria": False,
                            }
                        ))
                        description_buffer = []
                else:
                    # 아직 어떤 병명에도 속하지 않는 구간이면 스킵
                    continue

        # 모든 페이지 처리 후: 열려 있는 criteria 박스가 남아 있으면 flush
        if in_criteria_section and criteria_buffer and current_disorder:
            criteria_text = "\n".join(criteria_buffer)
            docs.append(Document(
                page_content=criteria_text,
                metadata={
                    "page": page_idx,  # 마지막으로 처리한 page_idx
                    "disorder": current_disorder,
                    "canonical_disorder": current_canonical_disorder,
                    "section": "criteria",
                    "is_criteria": True,
                }
            ))
            criteria_buffer = []
            in_criteria_section = False

        # 마지막 설명부 flush
        if current_disorder and description_buffer:
            big_text = "\n".join(description_buffer)
            docs.append(Document(
                page_content=big_text,
                metadata={
                    "page": page_idx,
                    "disorder": current_disorder,
                    "canonical_disorder": current_canonical_disorder,
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
