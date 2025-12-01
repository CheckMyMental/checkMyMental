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
    # 메세지 필드는 BaseMessage(대화히스토리)의 순서있는 모음이고, Annotated를 통해, 메타데이터가 붙는다. 
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    current_stage: Literal[
        "intake",
        "hypothesis",
        "validation",
        "severity_assessment",
        "solution",
    ]

    # continue : 다음 단계로 진행
    # wait_user : 사용자 응답 대기
    # end : 상담 종료
    next_action: Literal["continue", "wait_user", "end"]

    # Stage 1: intake
    turn_count: int #초기 정보 수집 단계
    summary_report: str #지금까지의 대화 내용을 요약한 텍스트를 저장
    intake_required_fields: Dict[str, object] #이번 상담에서 반드시 받아야 하는 정보 항목 정의
    intake_progress: Dict[str, object] #지금까지 유저에게서 수집한 값들을 저장하는 공간
    intake_missing_fields: List[str] #아직 못 받은 필드들의 이름 리스트

    # Stage 2: hypothesis
    rag_diagnosis_results: Dict[str, object] #RAG로 검색된 진단 결과(3개의 질환 후보군, 3개의 의심질환에 대한 판단기준 list)
    hypothesis_report: str #3가지 질환에 대해서 RAG와 진단1에서의 응답을 통해 스코어링 하고, 가설 리포트를 생성
    diagnosis_candidates: List[str] #가설 후보 질환명 리스트

    # Stage 3: validation
    validation_questions: List[Dict[str, str]]  #가설을 검증하기 위해 던질 질문리스트
    current_question_index: int #몇번째 질문을 하고 있는지 카운트
    user_answers: Dict[str, str] #각 validation 질문에 대한 유저의 답변 저장
    validated_diagnosis: str #최종 확정 질환명 -> [TODO] 심각도 단계로 넘어갈지 말지에 대한 로직 필요.

    # Stage 4: severity assessment
    severity_required: bool #이번 케이스에서 심각도 평가(설문)을 꼭 해야하는지에 대한 여부
    severity_survey_id: str #사용중인 설문 도구의 ID를 저장
    severity_responses: Dict[str, object] #유저의 설문 응답 및 설문 진행 관련 데이터를 저장
    severity_score: str #정량화된 점수(숫자)를 문자열 형태로 저장
    severity_level: str #점수를 등급으로 해석한 결과

    # Stage 5: solution
    rag_solution_results: Dict[str, object] #RAG로 가져온 해결책/가이드/컨텐츠 후보들
    final_response: str #유저에게 최종으로 보여줄 메세지
    symptoms_summary: str #유저가 호소한 증상을 정리한 요약문

