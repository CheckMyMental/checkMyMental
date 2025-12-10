import json
from typing import Literal
from graph.state import CounselingState


def check_intake_complete(state: CounselingState) -> Literal["hypothesis", "__end__"]:
    """
    Intake 단계 종료 조건 체크
    - 일반 Intake: intake_summary_report 생성 여부로 종료
    - Re-Intake: summary 기반 판단 금지 → 보강 질문 수행 개수로 판단
    """

    intake_summary = (
        state.get("intake_summary_report")  # 기본 intake
        or state.get("reinforced_intake_summary_report")  # re-intake 1
        or state.get("additional_intake_summary")  # re-intake 2
        or state.get("domain_specific_intake_summary")  # re-intake 3
        or state.get("deep_question_summary")  # re-intake 심화질문
    )
    is_re_intake = state.get("is_re_intake", False)
    asked = state.get("re_intake_questions_asked", 0)

    if is_re_intake:

        # 🔥 Re-Intake: 질문 3개 해야 다음 단계로 넘어갈 수 있음
        if asked >= 3:
            return "hypothesis"

        return "__end__"

    # 일반 Intake: summary 생성되면 완료
    if intake_summary:
        return "hypothesis"

    return "__end__"



def check_validation_outcome(state: CounselingState) -> Literal["severity", "intake", "__end__"]:
    """
    Validation 단계 종료 조건 및 다음 스테이지 분기
    """


    # 🔥 (1) Re-Intake 플래그가 있으면 무조건 Intake로
    if state.get("is_re_intake"):
        return "intake"

    # 🔥 (2) 확정 진단 있으면 Severity로
    if state.get("severity_diagnosis"):
        return "severity"

    # 🔥 (3) 확률 기반 자동 판단
    probabilities = state.get("validation_probabilities")
    if probabilities and isinstance(probabilities, dict):
        max_prob = 0.0
        top_diagnosis = None

        for d, p in probabilities.items():
            try:
                p_val = float(p)
                if p_val > max_prob:
                    max_prob = p_val
                    top_diagnosis = d
            except Exception:
                continue

        # 확률 50% 이하 → Re-Intake로 보내기
        if max_prob <= 0.5:
            return "intake"

        # 아니면 severity
        return "severity"

    return "__end__"



def check_severity_complete(state: CounselingState) -> Literal["solution", "__end__"]:
    """
    Severity → Solution 분기
    """

    severity_result = state.get("severity_result_string")

    if severity_result:
        return "solution"

    return "__end__"
