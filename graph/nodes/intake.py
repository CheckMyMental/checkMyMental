"""
Stage 1 (intake) 노드 스켈레톤.

TODO:
    - `frontend/chat_handler.process_user_input`에서 수행하던
      요약 생성/턴 카운트 로직을 이곳으로 이동.
"""

from __future__ import annotations

from ..state import CounselingState


def intake_node(state: CounselingState) -> CounselingState:
    """
    초기 정보 수집 단계.

    현재는 상태를 그대로 반환하며, Langraph 루프를 위한 최소 필드만 보장한다.
    """

    updated_state: CounselingState = dict(state)
    updated_state.setdefault("current_stage", "intake")
    updated_state.setdefault("next_action", "wait_user")

    return updated_state

