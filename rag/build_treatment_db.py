# rag/build_treatment_db.py

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

from rag.config import (
    TREATMENT_DOCS_DIR,
    TREATMENT_PDF_FILES,
    CHROMA_DIR,
    TREATMENT_COLLECTION_NAME,
)
from rag.embeddings import get_embeddings


def chunk_text(text: str, max_chars: int = 900):
    chunks = []
    buf = []
    cur_len = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if cur_len + len(line) > max_chars:
            chunks.append(" ".join(buf))
            buf = [line]
            cur_len = len(line)
        else:
            buf.append(line)
            cur_len += len(line)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


# 💡 DSM → Treatment Category 매칭을 위해
# Treatment DB의 metadata["disorder"] 값을 '상위 카테고리'로 통일한다.
PDF_TO_DISORDER = {
    "ocd.pdf": "Obsessive-Compulsive and Related Disorders",
    "depression.pdf": "Depressive Disorders",
    "anxietyandpanic.pdf": "Anxiety Disorders",
    "bipolar.pdf": "Bipolar and Related Disorders",
    "ptsd.pdf": "Posttraumatic Stress Disorder",
    "adhd.pdf": "Attention-Deficit/Hyperactivity Disorder",
}


def main():
    print("[treatment] Reading treatment PDFs...")
    embeddings = get_embeddings()
    docs = []

    for filename in TREATMENT_PDF_FILES:
        pdf_path = os.path.join(TREATMENT_DOCS_DIR, filename)
        if not os.path.exists(pdf_path):
            print(f"  ! Skip (not found): {pdf_path}")
            continue

        disorder_meta = PDF_TO_DISORDER.get(filename)
        if disorder_meta is None:
            # 혹시 매핑 안 된 PDF가 있으면 파일명 그대로 사용
            disorder_meta = os.path.splitext(filename)[0]

        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        chunks = chunk_text(full_text)
        print(f"  -> {filename}: {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source_pdf": filename,
                        "disorder": disorder_meta,  # ⬅️ 이게 최종 검색 key!
                        "chunk_id": i,
                        "section": "treatment",
                        "lang": "en",
                    },
                )
            )

    print(f"[treatment] Total {len(docs)} chunks. Saving to Chroma...")

    db = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=TREATMENT_COLLECTION_NAME,
    )
    db.persist()
    print("[treatment] ✅ Done. Collection name:", TREATMENT_COLLECTION_NAME)
    print("Saved to:", CHROMA_DIR)


if __name__ == "__main__":
    main()
