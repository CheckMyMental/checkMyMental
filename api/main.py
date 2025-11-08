# api/main.py

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from api.rag_service import retrieve_candidates, retrieve_solution

app = FastAPI(title="DSM RAG API")


# ---------- Stage 2: Hypothesis Generation ----------
class HypothesisReq(BaseModel):
    intake_report: str
    top_k: Optional[int] = 12
    diag_top_n: Optional[int] = 3


@app.post("/rag/hypothesis")
def rag_hypothesis(req: HypothesisReq):
    data = retrieve_candidates(
        symptom_text=req.intake_report,
        top_k=req.top_k or 12,
        diag_top_n=req.diag_top_n or 3,
    )
    # 이름은 기존이랑 맞춰 둘게
    data["hypothesis_report"] = "Top DSM candidates: " + ", ".join(
        data["diagnosis_candidates"]
    )
    return data


# ---------- Stage 4: Solution & Summary ----------
class SolutionReq(BaseModel):
    diagnosis: str


@app.post("/rag/solution")
def rag_solution(req: SolutionReq):
    return retrieve_solution(req.diagnosis)
