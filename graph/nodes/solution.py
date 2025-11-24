"""
Stage 4 (solution/summary) 노드 스켈레톤.

TODO:
    - `frontend/rag_handler.process_stage4_rag_solution`과
      Gemini 최종 응답 생성을 여기로 옮긴다.
"""

from __future__ import annotations

from ..state import CounselingState


def solution_node(state: CounselingState) -> CounselingState:
    """확정 진단 기반 최종 요약/가이던스를 생성하는 노드."""

    updated_state: CounselingState = dict(state)
    updated_state["current_stage"] = "solution"
    updated_state.setdefault("final_response", "")
    updated_state["next_action"] = "end"

    return updated_state

