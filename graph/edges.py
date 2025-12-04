from typing import Literal
from graph.state import CounselingState

def check_intake_complete(state: CounselingState) -> Literal["hypothesis", "__end__"]:
    """
    Intake 단계 완료 여부 확인
    - intake_summary_report가 생성되었으면 Hypothesis 단계로 이동
    - 그렇지 않으면 Intake 단계 유지 (사용자 입력 대기) -> LangGraph에서는 END로 반환하여 사용자 입력을 기다림
      (단, 여기서는 Human-in-the-loop 구조가 아니므로 바로 루프를 돌면 안 됨.
       LangGraph의 일반적인 챗봇 패턴: Node 실행 -> 응답 생성 -> END (사용자 입력 대기)
       따라서 여기서는 '다음 단계로 넘어갈지 말지'를 결정하는 것이 아니라, 
       '정보 수집이 완료되었으니 즉시 다음 노드를 실행할지'를 결정해야 함.)
    """
    # 요약 리포트가 있으면 정보 수집 완료 -> Hypothesis로 자동 진행
    if state.get("intake_summary_report"):
        return "hypothesis"
    
    # 아직 정보 수집 중 -> 사용자 입력을 받기 위해 멈춤
    return "__end__"

def check_validation_outcome(state: CounselingState) -> Literal["severity", "intake", "__end__"]:
    """
    Validation 결과에 따른 분기 처리
    - is_re_intake가 True면 -> Intake (Re-Intake 모드)
    - severity_diagnosis가 있으면 -> Severity
    - 둘 다 아니면 -> Validation 유지 (사용자 응답 대기) -> END
    """
    # 1. 재탐색(Re-Intake) 결정된 경우
    if state.get("is_re_intake"):
        return "intake"
    
    # 2. 확정 진단명이 나온 경우 -> Severity 단계로 이동
    if state.get("severity_diagnosis"):
        return "severity"
    
    # 3. 아직 검증 진행 중 (질문-답변 루프) -> 사용자 입력을 받기 위해 멈춤
    return "__end__"

def check_severity_complete(state: CounselingState) -> Literal["solution", "__end__"]:
    """
    Severity 단계 완료 여부 확인
    - severity_result_string이 생성되었으면 Solution 단계로 이동
    - 그렇지 않으면 Severity 단계 유지 (질문-답변 루프) -> END
    """
    if state.get("severity_result_string"):
        return "solution"
    
    return "__end__"

