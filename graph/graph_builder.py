"""
Langraph StateGraph 구성 스켈레톤.

실제 로직은 `frontend/chat_handler.py` 및 `frontend/stage_handler.py`
에서 분리한 기능을 노드 함수로 옮기면서 채워 넣는다.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .edges import (
    route_after_validation,
    should_continue_intake,
    should_continue_severity,
    should_continue_validation,
)
from .nodes.hypothesis import hypothesis_node
from .nodes.intake import intake_node
from .nodes.severity import severity_assessment_node
from .nodes.solution import solution_node
from .nodes.validation import (
    validation_collect_node,
    validation_finalize_node,
    validation_question_node,
)
from .state import CounselingState

__all__ = ["build_counseling_graph"]


def build_counseling_graph():
    """
    상담 파이프라인용 Langraph StateGraph 인스턴스를 컴파일한다.

    Returns:
        Compiled graph ready to `stream()` or `invoke()`.
    """

    workflow = StateGraph(CounselingState)

    # 노드 등록
    workflow.add_node("intake", intake_node)
    workflow.add_node("hypothesis", hypothesis_node)
    workflow.add_node("validation_question", validation_question_node)
    workflow.add_node("validation_collect", validation_collect_node)
    workflow.add_node("validation_finalize", validation_finalize_node)
    workflow.add_node("severity_assessment", severity_assessment_node)
    workflow.add_node("solution", solution_node)

    workflow.set_entry_point("intake")


    # 엣지 등록
    # Stage 1: intake ↔ hypothesis
    workflow.add_conditional_edges(
        "intake",
        should_continue_intake,
        {
            "intake": "intake",
            "hypothesis": "hypothesis",
        },
    )

    # Stage 2 → Stage 3
    workflow.add_edge("hypothesis", "validation_question")

    # Stage 3 내부 루프
    workflow.add_edge("validation_question", "validation_collect")
    workflow.add_conditional_edges(
        "validation_collect",
        should_continue_validation,
        {
            "collect": "validation_collect",
            "finalize": "validation_finalize",
        },
    )

    # Stage 4 (severity) 및 Stage 5 (solution)
    workflow.add_conditional_edges(
        "validation_finalize",
        route_after_validation,
        {
            "severity_assessment": "severity_assessment",
            "solution": "solution",
        },
    )

    workflow.add_conditional_edges(
        "severity_assessment",
        should_continue_severity,
        {
            "severity_assessment": "severity_assessment",
            "solution": "solution",
        },
    )

    workflow.add_edge("solution", END)

    return workflow.compile()

