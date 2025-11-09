# rag/config.py

# Chroma DB 저장 위치
CHROMA_DIR = "./rag/chroma_db"

# DSM-5-TR PDF 파일 위치 (프로젝트 루트에 있다고 가정)
DSM_PDF_PATH = "./documents/DSM-5-TR.pdf"

# 컬렉션 이름
DSM_COLLECTION_NAME = "dsm5tr"


# treatment
TREATMENT_DOCS_DIR = "./documents"
TREATMENT_PDF_FILES = [
    "ocd.pdf",
    "depression.pdf",
    "anxietyandpanic.pdf",
    "bipolar.pdf",
    "ptsd.pdf",
]
TREATMENT_COLLECTION_NAME = "treatment"