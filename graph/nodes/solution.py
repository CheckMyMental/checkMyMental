import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_gemini
from frontend.context_handler import load_context_from_file, load_prompt_from_file
from api.rag_service import retrieve_solution

def solution_node(state: CounselingState) -> Dict[str, Any]:
    """
    Solution Stage (5단계) 처리 노드
    - Intake, Validation, Severity 단계의 결과 통합 요약
    - RAG 검색을 통한 맞춤형 솔루션 도출
    - 최종 사용자 응답 생성
    """
    print("=" * 60)
    print("[Stage 5: Solution] 노드 실행 시작")
    print("=" * 60)
    
    # 1. 필수 데이터 확인
    diagnosis = state.get("severity_diagnosis")
    if not diagnosis:
        return {"messages": [AIMessage(content="오류: 최종 진단명이 없습니다.")]}
    
    # ⚠️ 중요: Severity 단계가 완료되지 않았으면 Solution 단계로 오면 안 됨
    severity_result = state.get("severity_result_string")
    if not severity_result:
        error_msg = "오류: 심각도 평가가 완료되지 않았습니다. 심각도 평가 단계를 먼저 진행해야 합니다."
        print(f"[Solution Node] ✗ {error_msg}")
        return {"messages": [AIMessage(content=error_msg)]}
        
    intake_summary = state.get("intake_summary_report", "")
    
    # 통합 요약문 생성 (Final Summary String)
    final_summary_parts = []
    if intake_summary:
        final_summary_parts.append(f"### 초기 면담 요약\n{intake_summary}")
    if severity_result:
        final_summary_parts.append(f"### 심각도 평가 결과\n{severity_result}")
        
    final_summary_string = "\n\n".join(final_summary_parts)
    
    # 2. RAG 솔루션 검색
    # api.rag_service.retrieve_solution 사용
    try:
        rag_result = retrieve_solution(
            diagnosis=diagnosis,
            symptom_text=intake_summary # 증상 텍스트도 함께 제공하여 검색 정확도 향상
        )
    except Exception as e:
        print(f"Solution RAG 검색 오류: {e}")
        rag_result = {"solutions": []}
        
    # 검색된 솔루션 텍스트 포맷팅
    solutions = rag_result.get("solutions", [])
    solution_text_parts = []
    for i, sol in enumerate(solutions, 1):
        text = sol.get("text", "").strip()
        if text:
            solution_text_parts.append(f"#### 참고 자료 {i}\n{text}")
            
    rag_solution_context = "\n\n".join(solution_text_parts)
    if not rag_solution_context:
        rag_solution_context = "(관련 솔루션 자료를 찾지 못했습니다. 일반적인 정신 건강 지침을 제공해주세요.)"

    # 3. 프롬프트 및 컨텍스트 로드
    base_prompt = load_prompt_from_file("stage5_solution.md")
    if not base_prompt:
        base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        print(f"[Solution Node] ⚠ 프롬프트 파일 로드 실패: stage5_solution.md")
        
    solution_context_guide = load_context_from_file("stage_specific/context_stage5_solution.json")

    # 4. 시스템 지시사항 구성
    system_instructions = f"""
{base_prompt}

## 최종 진단명: {diagnosis}

## 상담 전체 요약 (Final Summary)
{final_summary_string}

## RAG 검색된 솔루션 자료
{rag_solution_context}

## 솔루션 작성 가이드라인
{solution_context_guide}

## 지시사항
위 정보를 종합하여 사용자에게 최종 결과 리포트를 작성해주세요.
1. **진단 및 공감**: 사용자의 어려움을 인정하고 위로하며 진단 결과를 조심스럽게 전달하세요.
2. **증상 요약**: 사용자가 호소했던 주요 증상을 간략히 언급하세요.
3. **맞춤형 솔루션**: RAG 자료를 참고하여 실질적인 조언을 3가지 이상 제시하세요.
4. **마무리**: 희망적인 메시지로 끝맺으세요.

출력은 오직 **사용자에게 보여질 최종 메시지**만 작성하면 됩니다. 내부 데이터 태그는 필요 없습니다.
"""

    # 5. LLM 호출
    # Solution 단계는 대화형이 아니라 일방적인 리포트 생성이므로
    # 히스토리를 참고하되, 사용자 입력은 별도로 필요하지 않음.
    # ask_gemini 호출 시 user_input을 빈 문자열이나 지시어로 대체 가능.
    
    messages = state['messages']
    history = [{"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content} for m in messages]
    
    response_text = ask_gemini(
        user_input="최종 솔루션 리포트를 작성해주세요.",
        context=system_instructions,
        conversation_history=history
    )
    
    # 6. 결과 반환
    return {
        "messages": [AIMessage(content=response_text)],
        "final_summary_string": final_summary_string,
        "solution_content": response_text
    }

