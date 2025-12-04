from langgraph.graph import StateGraph, END
from graph.state import CounselingState
from graph.nodes.intake import intake_node
from graph.nodes.hypothesis import hypothesis_node
from graph.nodes.validation import validation_node
from graph.nodes.severity import severity_node
from graph.nodes.solution import solution_node
from graph.edges import (
    check_intake_complete,
    check_validation_outcome,
    check_severity_complete
)

def build_graph():
    """
    상담 프로세스 전체 그래프 구성
    
    Flow:
    1. Intake (반복) -> (완료 시) -> Hypothesis
    2. Hypothesis (자동) -> Validation
    3. Validation (반복) -> (확률 낮음) -> Re-Intake (Intake로 복귀)
                        -> (확률 높음) -> Severity
    4. Severity (반복) -> (완료 시) -> Solution
    5. Solution (자동) -> END
    """
    
    # 1. 그래프 초기화
    workflow = StateGraph(CounselingState)
    
    # 2. 노드 추가
    workflow.add_node("intake", intake_node)
    workflow.add_node("hypothesis", hypothesis_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("severity", severity_node)
    workflow.add_node("solution", solution_node)
    
    # 3. 엣지 연결
    
    # 시작점 -> Intake
    workflow.set_entry_point("intake")
    
    # Intake -> (조건부) -> Hypothesis or END(대기)
    workflow.add_conditional_edges(
        "intake",
        check_intake_complete,
        {
            "hypothesis": "hypothesis",
            "__end__": END
        }
    )
    
    # Hypothesis -> Validation (무조건 이동)
    # Hypothesis는 내부 처리 노드이므로 사용자 입력 대기 없이 바로 다음으로
    workflow.add_edge("hypothesis", "validation")
    
    # Validation -> (조건부) -> Intake(Re-Intake) or Severity or END(대기)
    workflow.add_conditional_edges(
        "validation",
        check_validation_outcome,
        {
            "intake": "intake",
            "severity": "severity",
            "__end__": END
        }
    )
    
    # Severity -> (조건부) -> Solution or END(대기)
    workflow.add_conditional_edges(
        "severity",
        check_severity_complete,
        {
            "solution": "solution",
            "__end__": END
        }
    )
    
    # Solution -> END (상담 종료)
    workflow.add_edge("solution", END)
    
    # 4. 그래프 컴파일
    # 메모리(Checkpointer)는 외부에서 주입하거나 여기서 설정 가능
    # 여기서는 순수 그래프 구조만 반환
    return workflow.compile()

# 그래프 인스턴스 생성 (import해서 사용 가능)
graph = build_graph()

