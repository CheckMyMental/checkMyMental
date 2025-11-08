# rag/embeddings.py

from langchain_community.embeddings import HuggingFaceEmbeddings

def get_embeddings():
    # Jina v3는 remote code 허용 필요
    return HuggingFaceEmbeddings(
        model_name="jinaai/jina-embeddings-v3",
        model_kwargs={"trust_remote_code": True}
    )
