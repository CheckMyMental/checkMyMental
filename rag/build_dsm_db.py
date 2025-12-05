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

# -------- 패턴들 --------
ICD_PATTERN = re.compile(r"^F\d{2}(\.\d+)?$")
CRITERIA_PATTERN = re.compile(r"^[A-Z]\.\s")
SUBCRITERIA_PATTERN = re.compile(r"^\d+\.\s")


def looks_like_disorder_title(text: str) -> bool:
    """
    병명 타이틀의 형태적 특징을 대강 필터링.
    (진짜 확인은 KNOWN_DISORDERS fuzzy 매칭에서 한다)
    """
    text = text.strip()
    if not text:
        return False
    if len(text) > 150:
        return False

    words = text.split()
    # 단어 수는 꽤 길 수도 있어서 상한만 느슨하게 둔다.
    if len(words) > 20:
        return False

    # 첫 글자가 대문자인 단어 비율이 어느 정도 이상이면 타이틀로 본다.
    cap_ratio = sum(1 for w in words if w[0].isupper()) / len(words)
    if cap_ratio < 0.6:
        return False
    return True


def group_words_to_lines(words, y_tolerance=3.0):
    """
    pdfplumber words 리스트를 y 좌표(top) 기준으로 줄 단위로 묶기.
    """
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
# 본문 섹션 헤더 감지
# ----------------------

def looks_like_section_header(text: str, x0: float, page_width: float) -> bool:
    """
    Diagnostic Features / Prevalence / Development and Course 등
    DSM 본문 섹션 제목만 골라내기 위한 함수.

    - 'Manic Episode', 'Tourette’s Disorder' 같은 것은 절대 헤더로
      인식되지 않게 모양이 아니라 '내용'으로만 판단한다.
    """
    t = text.strip()
    if not t:
        return False

    # 맨 끝 콜론 제거: "Diagnostic Features:" 같은 경우
    base = t.rstrip(":")
    base_norm = re.sub(r"\s+", " ", base).lower()

    # DSM 본문에서 criteria 박스 직후에 나오는 대표 섹션들
    HEADER_PREFIXES = [
        "diagnostic features",
        "associated features supporting diagnosis",
        "associated features supporting the diagnosis",
        "prevalence",
        "development and course",
        "risk and prognostic factors",
        "culture-related diagnostic issues",
        "gender-related diagnostic issues",
        "suicide risk",
        "functional consequences of",
        "differential diagnosis",
        "comorbidity",
    ]

    if not any(base_norm.startswith(p) for p in HEADER_PREFIXES):
        return False

    # 헤더는 보통 페이지 왼쪽에 붙어 있음(너무 오른쪽이면 제외)
    if x0 > page_width * 0.4:
        return False

    return True


def main():
    print("[1] PDF 읽는 중...")

    docs: list[Document] = []
    embeddings = get_embeddings()

    candidate_disorder = None          # Diagnostic Criteria 나오기 전까지의 '후보' 병명(raw)
    current_disorder = None            # 실제 메타데이터에 들어갈 병명(raw)
    current_canonical_disorder = None  # KNOWN_DISORDERS 기준 canonical 이름
    in_criteria_section = False

    criteria_buffer: list[str] = []    # 현재 criteria 박스 전체 텍스트
    description_buffer: list[str] = [] # 현재 병명에 대한 설명 텍스트
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
            skip_until_idx = -1  # 두 줄짜리/여러 줄 병명 타이틀 처리용

            for idx, line in enumerate(lines):
                if idx <= skip_until_idx:
                    continue

                text = line["text"].strip()
                x0 = line["x0"]
                x1 = line["x1"]

                # 오른쪽 정렬(또는 오른쪽에 몰려 있는) 한 줄 → 병명 타이틀 후보
                right_like = (x1 > width * 0.85) or (x0 > width * 0.6 and len(text) < 150)

                # 0) 이미 criteria 박스 안에 있는 경우 → 우선 '끝나는 조건'부터 체크
                if in_criteria_section and current_disorder:
                    # 0-1) 본문 섹션 헤더가 나오면 → 지금까지가 criteria 박스 전체
                    if looks_like_section_header(text, x0, width):
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
                        # 이 줄은 description에도 넣지 않고 건너뜀
                        continue

                    # 0-2) 헤더는 아니지만, 새로운 병명 타이틀이 시작되면
                    #      (헤더 없이 곧바로 다음 disorder로 넘어가는 케이스)
                    if right_like and looks_like_disorder_title(text):
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
                        # 여기서 continue 하지 않고 아래 병명 후보 로직으로 떨어지게 둔다.
                    else:
                        # 아직 criteria 박스 내부 텍스트
                        criteria_buffer.append(text)
                        continue

                # 1) 오른쪽 한 줄짜리(또는 여러 줄짜리) → 병명 '후보'
                if right_like and looks_like_disorder_title(text):
                    # 여러 줄로 나뉜 병명 타이틀(예: Major or Mild ... / Parkinson’s Disease)을
                    # 한 줄로 합친다.
                    combined = text
                    j = idx + 1
                    while j < len(lines):
                        next_line = lines[j]
                        n_text = next_line["text"].strip()
                        n_x0 = next_line["x0"]
                        n_x1 = next_line["x1"]
                        if not n_text:
                            j += 1
                            continue
                        n_right_like = (n_x1 > width * 0.85) or (n_x0 > width * 0.6 and len(n_text) < 150)
                        if n_right_like and looks_like_disorder_title(n_text):
                            combined = combined + " " + n_text
                            j += 1
                        else:
                            break
                    if j > idx + 1:
                        skip_until_idx = j - 1  # 합쳐진 줄들은 이후 루프에서 건너뛴다.

                    title_text = combined

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

                    candidate_disorder = title_text
                    # 아직 KNOWN_DISORDERS 매칭은 안 하고,
                    # 'Diagnostic Criteria' 줄에서 실제 current_disorder로 승격시킨다.
                    continue

                # 2) "Diagnostic Criteria" 줄 → 병명 확정 + criteria 박스 시작
                if "Diagnostic Criteria" in text:
                    # (원하면 여기서 ICD 코드도 추출 가능)
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
                            # 매칭 실패하면 current_disorder는 그대로(이전 병명 유지) or None
                        candidate_disorder = None

                    in_criteria_section = True
                    criteria_buffer = []   # 박스 전체를 여기다 쌓는다
                    continue

                # 3) criteria 모드가 아니고, 본문 섹션 헤더가 나오면 → 그냥 스킵
                if looks_like_section_header(text, x0, width):
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
