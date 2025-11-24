"""
Stage 4 (severity assessment) 노드 스켈레톤.

TODO:
    - Stage 3 출력과 백엔드 설문 데이터베이스를 연결하여
      필요한 설문지를 로드하고 사용자에게 제시한다.
"""

from __future__ import annotations

from ..state import CounselingState


def severity_assessment_node(state: CounselingState) -> CounselingState:
    """
    심각도 설문지를 제시하고 응답을 수집하는 노드.

    실제 구현에서는 DB/RAG에서 설문 문항을 불러오고, 사용자 응답을
    `severity_responses`에 저장한 뒤 백엔드 점수 계산 결과를 기다린다.
    """

    updated_state: CounselingState = dict(state)
    updated_state["current_stage"] = "severity_assessment"
    updated_state.setdefault("severity_required", False)
    updated_state.setdefault("severity_survey_id", "")
    updated_state.setdefault("severity_responses", {})
    updated_state.setdefault("severity_score", "")
    updated_state.setdefault("severity_level", "")
    updated_state["next_action"] = "wait_user"

    return updated_state

