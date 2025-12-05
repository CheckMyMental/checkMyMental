# rag/add_treatment_pdf.py

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

from rag.embeddings import get_embeddings
from rag.config import CHROMA_DIR, TREATMENT_COLLECTION_NAME


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


def main(pdf_path: str, disorder_name: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    print(f"[add] reading {pdf_path} ...")

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    chunks = chunk_text(full_text)
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "source_pdf": os.path.basename(pdf_path),
                    "disorder": disorder_name,  # <-- 새로 추가한 PDF가 다루는 병명 한 개
                    "chunk_id": i,
                    "section": "treatment",
                    "lang": "en",
                },
            )
        )

    print(f"[add] created {len(docs)} chunks")

    # 기존 treatment 컬렉션 열기
    embeddings = get_embeddings()
    db = Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=TREATMENT_COLLECTION_NAME,
    )

    db.add_documents(docs)
    db.persist()
    print("[add] done.")


if __name__ == "__main__":
    # 예: python rag/add_treatment_pdf.py ./documents/socialanxiety.pdf "Social Anxiety Disorder"
    if len(sys.argv) < 3:
        print("Usage: python rag/add_treatment_pdf.py <pdf_path> <disorder_name>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    disorder_name = " ".join(sys.argv[2:])
    main(pdf_path, disorder_name)
