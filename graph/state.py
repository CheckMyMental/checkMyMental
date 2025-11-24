"""
Langraph에서 사용할 상담 파이프라인 전역 상태 정의.

NOTE:
    - 기존 `frontend/stage_handler.StageHandler`와
      `frontend/chat_handler`에서 관리하던 session_state를
      순차적으로 이 TypedDict로 이전할 예정입니다.
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class CounselingState(TypedDict, total=False):
    """
    Langraph StateGraph에서 활용할 공용 상태 컨테이너.

    TODO:
        - 각 필드는 chat_handler/stage_handler 리팩토링 과정에서
          실제 데이터 구조에 맞춰 확정합니다.
    """

    # 공통 메타 정보
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_stage: Literal[
        "intake",
        "hypothesis",
        "validation",
        "severity_assessment",
        "solution",
    ]
    next_action: Literal["continue", "wait_user", "end"]

    # Stage 1: intake
    turn_count: int
    summary_report: str
    intake_required_fields: Dict[str, object]
    intake_progress: Dict[str, object]
    intake_missing_fields: List[str]

    # Stage 2: hypothesis
    rag_diagnosis_results: Dict[str, object]
    hypothesis_report: str
    diagnosis_candidates: List[str]

    # Stage 3: validation
    validation_questions: List[Dict[str, str]]
    current_question_index: int
    user_answers: Dict[str, str]
    validated_diagnosis: str

    # Stage 4: severity assessment
    severity_required: bool
    severity_survey_id: str
    severity_responses: Dict[str, object]
    severity_score: str
    severity_level: str

    # Stage 5: solution
    rag_solution_results: Dict[str, object]
    final_response: str
    symptoms_summary: str

