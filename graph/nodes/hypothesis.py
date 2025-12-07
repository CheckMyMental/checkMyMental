from typing import Dict, Any, List
import json
from langchain_core.messages import AIMessage
from graph.state import CounselingState
from api.rag_service import retrieve_candidates

def hypothesis_node(state: CounselingState) -> Dict[str, Any]:
    """
    Hypothesis Stage (2단계) 처리 노드
    - Intake 단계에서 생성된 요약 리포트를 입력으로 받음
    - RAG 검색을 통해 의심 질환 후보 및 진단 기준 도출
    - 다음 단계(Validation)를 위한 State 업데이트
    """
    print("=" * 60)
    print("[Stage 2: Hypothesis] 노드 실행 시작")
    print("=" * 60)
    
    # 1. 입력 데이터 확인 (Intake Summary Report)
    intake_summary = state.get("intake_summary_report")
    
    if not intake_summary:
        # 방어 코드: 요약 리포트가 없는 경우 (정상적인 흐름에서는 발생하지 않아야 함)
        error_msg = "오류: 상담 요약 리포트를 찾을 수 없습니다."
        return {
            "messages": [AIMessage(content=error_msg)],
            # 에러 상황이지만 프로세스 중단을 막기 위해 빈 리스트 설정
            "hypothesis_criteria": []
        }

    # 2. RAG 검색 수행
    # api.rag_service.retrieve_candidates 함수 사용
    # top_k=12 (검색 문서 수), diag_top_n=3 (최종 후보 질환 수)
    try:
        rag_result = retrieve_candidates(
            symptom_text=intake_summary,
            top_k=12,
            diag_top_n=3
        )
    except Exception as e:
        print(f"RAG 검색 중 오류 발생: {e}")
        return {
            "messages": [AIMessage(content="질환 데이터베이스 검색 중 문제가 발생했습니다.")],
            "hypothesis_criteria": []
        }

    # 3. 결과 파싱 및 State 업데이트 데이터 준비
    # retrieve_candidates의 반환 형식:
    # {
    #   "input_symptom": ...,
    #   "diagnosis_candidates": ["질환1", "질환2", "질환3"],
    #   "by_diagnosis": {
    #       "질환1": [{"text": "기준1", ...}, ...],
    #       ...
    #   }
    # }
    
    candidates = rag_result.get("diagnosis_candidates", [])
    by_diagnosis = rag_result.get("by_diagnosis", {})
    
    # hypothesis_criteria에 저장할 형식:
    # 단순 리스트보다는 다음 단계(Validation)에서 질문 생성에 활용하기 좋게 구성
    # 여기서는 State 정의에 따라 List[str] 형태로 저장하거나, 
    # 필요하다면 구조화된 데이터를 저장해야 함.
    # state.py 정의: hypothesis_criteria: Optional[List[str]]
    
    # 여기서는 각 질환별 진단 기준 텍스트를 리스트로 변환하여 저장
    criteria_list = []
    formatted_report_parts = []
    
    formatted_report_parts.append(f"### 분석된 의심 질환 (Top {len(candidates)})")
    
    for i, disease in enumerate(candidates, 1):
        formatted_report_parts.append(f"{i}. {disease}")
        
        # 해당 질환의 진단 기준 가져오기
        disease_criteria = by_diagnosis.get(disease, [])
        
        # State에 저장할 리스트에 추가 (질환명: 기준 내용 형태)
        for criteria in disease_criteria:
            text = criteria.get("text", "").strip()
            if text:
                criteria_list.append(f"[{disease}] {text}")
    
    # 사용자에게 보여줄 메시지 구성 (선택 사항, 보통 이 단계는 내부 처리 후 바로 넘어감)
    # 하지만 LangGraph 흐름상 메시지를 추가하는 것이 자연스러움
    report_text = "\n".join(formatted_report_parts)
    result_message = f"증상 분석 결과, 다음 {len(candidates)}가지 질환이 의심됩니다:\n\n{report_text}\n\n이제 각 질환에 대한 정밀 검증을 시작합니다."

    # 4. 결과 반환
    return {
        "messages": [AIMessage(content=result_message)],
        "hypothesis_criteria": criteria_list,
        # 다음 단계를 위해 의심 질환 리스트도 어딘가에 저장하면 좋겠지만, 
        # 현재 State 정의에는 명시적인 'candidate_diseases' 필드가 없음.
        # 필요하다면 criteria_list에서 파싱하거나 state.py를 수정해야 함.
        # 일단은 criteria_list에 질환명이 포함되어 있으므로 이를 활용.
    }

