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


# 매핑
PDF_TO_DISORDER = {
    "ocd.pdf": "Obsessive-Compulsive Disorder",
    "depression.pdf": "Major Depressive Disorder",
    "anxietyandpanic.pdf": "Generalized Anxiety Disorder / Panic Disorder",
    "bipolar.pdf": "Bipolar I Disorder / Bipolar II Disorder",
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
                        "disorder": disorder_meta,
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
