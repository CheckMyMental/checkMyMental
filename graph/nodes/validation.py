"""
Stage 3 (validation) 관련 노드 스켈레톤.

TODO:
    - 질문 생성/응답 수집/최종 검증 로직을
      `frontend/chat_handler`의 Stage 3 코드에서 옮겨온다.
"""

from __future__ import annotations

from ..state import CounselingState


def validation_question_node(state: CounselingState) -> CounselingState:
    """감별 질문 리스트를 생성하거나 재사용."""

    updated_state: CounselingState = dict(state)
    updated_state["current_stage"] = "validation"
    updated_state.setdefault("validation_questions", [])
    updated_state.setdefault("current_question_index", 0)
    updated_state.setdefault("next_action", "continue")

    return updated_state


def validation_collect_node(state: CounselingState) -> CounselingState:
    """
    사용자의 Likert 응답을 수집하는 노드.

    실제 구현에서는 사용자 입력 이벤트와 Human-in-the-loop를 연결한다.
    """

    updated_state: CounselingState = dict(state)
    updated_state.setdefault("user_answers", {})
    updated_state["next_action"] = "wait_user"

    return updated_state


def validation_finalize_node(state: CounselingState) -> CounselingState:
    """모든 답변을 토대로 확정 진단을 산출하는 노드."""

    updated_state: CounselingState = dict(state)
    updated_state["next_action"] = "continue"
    updated_state.setdefault("validated_diagnosis", "")

    return updated_state

