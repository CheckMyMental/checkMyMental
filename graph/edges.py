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
    intake_summary = state.get("intake_summary_report")
    if intake_summary:
        print(f"[Edges] ✓ Intake 완료 확인 - intake_summary_report 생성됨 (길이: {len(intake_summary)} 문자)")
        print(f"[Edges] → 다음 단계: Hypothesis")
        return "hypothesis"
    
    # 아직 정보 수집 중 -> 사용자 입력을 받기 위해 멈춤
    print(f"[Edges] ⏸ Intake 진행 중 - intake_summary_report 미생성, 사용자 입력 대기")
    print(f"[Edges] 현재 상태: domain_active={state.get('domain_questions_active', False)}, current_domain={state.get('current_domain', None)}")
    return "__end__"

def check_validation_outcome(state: CounselingState) -> Literal["severity", "intake", "__end__"]:
    """
    Validation 결과에 따른 분기 처리
    - is_re_intake가 True면 -> Intake (Re-Intake 모드)
    - severity_diagnosis가 있으면 -> Severity
    - 확률이 계산되었으면 확률 기반으로 자동 분기
    - 둘 다 아니면 -> Validation 유지 (사용자 응답 대기) -> END
    """
    print(f"[Edges] Validation 결과 확인 시작...")
    print(f"  - is_re_intake: {state.get('is_re_intake')}")
    print(f"  - severity_diagnosis: {state.get('severity_diagnosis')}")
    print(f"  - validation_probabilities: {state.get('validation_probabilities')}")
    
    # 1. 재탐색(Re-Intake) 결정된 경우
    if state.get("is_re_intake"):
        print(f"[Edges] ✓ Validation → Re-Intake 결정 (is_re_intake=True)")
        return "intake"
    
    # 2. 확정 진단명이 나온 경우 -> Severity 단계로 이동
    if state.get("severity_diagnosis"):
        print(f"[Edges] ✓ Validation → Severity 결정 (severity_diagnosis={state.get('severity_diagnosis')})")
        return "severity"
    
    # 3. 확률이 이미 계산되었으면 확률 기반으로 자동 분기 (중요!)
    probabilities = state.get("validation_probabilities")
    if probabilities and isinstance(probabilities, dict) and len(probabilities) > 0:
        print(f"[Edges] 확률 계산 완료 확인: {probabilities}")
        # 확률 중 최대값 찾기
        max_prob = 0.0
        top_diagnosis = None
        for diagnosis, prob in probabilities.items():
            try:
                prob_val = float(prob) if not isinstance(prob, (int, float)) else prob
                if prob_val > max_prob:
                    max_prob = prob_val
                    top_diagnosis = diagnosis
            except (ValueError, TypeError):
                continue
        
        # 확률 기반 자동 분기
        if max_prob <= 0.5:
            print(f"[Edges] ✓ Validation → Re-Intake 결정 (최대 확률: {max_prob} <= 0.5)")
            return "intake"
        else:
            print(f"[Edges] ✓ Validation → Severity 결정 (최대 확률: {max_prob}, Top 질환: {top_diagnosis})")
            return "severity"
    
    # 4. 아직 검증 진행 중 (질문-답변 루프) -> 사용자 입력을 받기 위해 멈춤
    print(f"[Edges] ⏸ Validation 진행 중 - 사용자 입력 대기")
    return "__end__"

def check_severity_complete(state: CounselingState) -> Literal["solution", "__end__"]:
    """
    Severity 단계 완료 여부 확인
    - severity_result_string이 생성되었으면 Solution 단계로 이동
    - 그렇지 않으면 Severity 단계 유지 (질문-답변 루프) -> END
    """
    severity_result = state.get("severity_result_string")
    print(f"[Edges] Severity 결과 확인:")
    print(f"  - severity_result_string: {severity_result[:100] if severity_result else None}...")
    
    if severity_result:
        print(f"[Edges] ✓ Severity 완료 확인 - severity_result_string 생성됨")
        print(f"[Edges] → 다음 단계: Solution")
        return "solution"
    
    print(f"[Edges] ⏸ Severity 진행 중 - severity_result_string 미생성, 사용자 입력 대기")
    return "__end__"

