"""
Langraph 조건부 엣지 판단 함수 모음.

NOTE:
    - 실제 판단 로직은 기존 `StageHandler.should_transition` 등의
      규칙을 이식하면서 확장될 예정입니다.
"""

from __future__ import annotations

from typing import Literal

from .state import CounselingState

__all__ = ["should_continue_intake", "should_continue_validation"]


def should_continue_intake(state: CounselingState) -> Literal["intake", "hypothesis"]:
    """
    Stage 1에서 다음 단계로 넘어갈지 여부를 반환.

    현재는 요약 보고서 존재 여부와 턴 수만을 기준으로 한다.
    """

    summary = state.get("summary_report")
    turn_count = state.get("turn_count", 0)

    if summary and turn_count >= 3:
        return "hypothesis"
    return "intake"


def should_continue_validation(state: CounselingState) -> Literal["collect", "finalize"]:
    """
    Stage 3의 감별 질문 루프를 제어.

    모든 질문에 답변이 끝나면 finalize, 아니면 계속 collect.
    """

    questions = state.get("validation_questions") or []
    index = state.get("current_question_index", 0)

    if questions and index >= len(questions):
        return "finalize"
    return "collect"

