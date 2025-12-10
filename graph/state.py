from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages

class CounselingState(TypedDict):
    """
    상담 전체 과정을 관리하는 상태 정의
    
    Attributes:
        messages: 대화 기록 (LangGraph 표준)
        
        # Intake Stage (1단계)
        intake_summary_report: 1단계 요약 리포트
        domain_questions_active: 도메인 심화 질문 모드 활성화 여부
        current_domain: 현재 탐색 중인 도메인 정보
        
        # Hypothesis Stage (2단계)
        hypothesis_criteria: RAG 검색 결과로 얻은 의심 질환별 판단 기준 리스트
        
        # Validation Stage (3단계)
        validation_probabilities: 각 의심 질환별 계산된 확률값
        is_re_intake: 확률 50% 이하로 인한 재탐색 모드 여부
        
        # Severity Stage (4단계)
        severity_diagnosis: 심각도 평가 대상 질환명 (Top 1)
        severity_result_string: 심각도 평가 결과 문자열
        
        # Solution Stage (5단계)
        final_summary_string: 1, 3, 4단계 통합 요약문
        solution_content: 최종 제공할 솔루션 내용
    """
    
    # Base
    messages: Annotated[List[Any], add_messages]  # 대화 기록 (HumanMessage, AIMessage 등)
    
    # Intake Stage (1단계: 초기 면담)
    intake_summary_report: Optional[str]  # 수집된 필수 정보 요약 리포트
    domain_questions_active: bool         # 도메인 심화 질문 모드 활성화 여부 (True: 활성, False: 비활성)
    current_domain: Optional[str]         # 현재 심화 질문 진행 중인 도메인 (예: "Depressive Disorders")
    
    # Hypothesis Stage (2단계: 가설 설정)
    hypothesis_criteria: Optional[List[str]]  # RAG 검색으로 도출된 의심 질환별 판단 기준 리스트
    
    # Validation Stage (3단계: 검증)
    validation_probabilities: Optional[Dict[str, float]]  # 각 의심 질환에 대한 검증 확률 (예: {"우울증": 0.8})
    is_re_intake: bool                                    # 확률이 낮아(50% 이하) 재탐색이 필요한지 여부
    # 질문 생성/진행용 내부 상태
    validation_questions: Optional[List[Dict[str, Any]]]  # 미리 생성된 질문 리스트
    validation_current_index: int                         # 다음에 물어볼 질문 인덱스 (0-based)
    validation_answers: Optional[List[int]]               # 각 질문에 대한 사용자의 1~5점 응답
    
    # Severity Stage (4단계: 심각도 평가)
    severity_diagnosis: Optional[str]      # 심각도 평가 대상으로 선정된 질환명 (Top 1)
    severity_result_string: Optional[str]  # 심각도 평가 결과 텍스트
    
    # Solution Stage (5단계: 솔루션)
    final_summary_string: Optional[str]  # 전체 상담 과정(1, 3, 4단계) 요약문
    solution_content: Optional[str]      # 사용자에게 제공할 최종 솔루션 내용

