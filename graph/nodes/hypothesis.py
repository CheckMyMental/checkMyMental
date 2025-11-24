"""
Stage 2 (hypothesis generation) 노드 스켈레톤.

TODO:
    - `frontend/rag_handler.process_stage2_rag_hypothesis` 호출과
      Gemini 응답 파싱을 이곳으로 이동.
"""

from __future__ import annotations

from ..state import CounselingState


def hypothesis_node(state: CounselingState) -> CounselingState:
    """
    Stage 1 요약을 기반으로 RAG + LLM 가설을 생성하는 자리.

    현재는 상태 마커만 갱신한다.
    """

    updated_state: CounselingState = dict(state)
    updated_state["current_stage"] = "hypothesis"
    updated_state.setdefault("next_action", "continue")

    return updated_state

