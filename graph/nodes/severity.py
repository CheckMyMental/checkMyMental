import json
from pathlib import Path
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file

def severity_node(state: CounselingState) -> Dict[str, Any]:
    """
    Severity Stage (4단계) 처리 노드
    - 확정된 1개 질환에 대한 심각도 평가 수행
    - 질환별 특화된 심각도 컨텍스트 로드 (있는 경우)
    - 질문 생성 및 응답 수집 루프
    - 최종 심각도 평가 결과 생성
    """
    
    messages = state['messages']
    last_message = messages[-1] if messages else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 1. 확정된 질환명 확인
    target_diagnosis = state.get("severity_diagnosis")
    if not target_diagnosis:
        return {"messages": [AIMessage(content="오류: 심각도 평가 대상 질환이 설정되지 않았습니다.")]}
    
    # 2. 질환별 심각도 Context 동적 로드 시도
    # 예: "Depression" -> "contexts/diseases/depression.json"
    # 파일명이 일치하지 않을 수 있으므로 키워드 매칭 시도하거나, 
    # 단순히 기본 심각도 가이드라인만 사용할 수도 있음.
    # 여기서는 간단한 매핑 로직 예시 적용
    
    disease_context = ""
    try:
        # 질환명에서 핵심 단어 추출 (간단히 소문자화하여 파일 찾기 시도)
        # 실제로는 더 정교한 매핑이 필요할 수 있음 (Mapping DB 등)
        # 여기서는 contexts/diseases/ 폴더를 검색
        disease_key = target_diagnosis.split()[0].lower() # 첫 단어 사용 (예: "Depressive" -> "depressive")
        
        # 매핑 테이블 (예시)
        mapping = {
            "depressive": "depression.json",
            "depression": "depression.json",
            "anxiety": "anxiety.json",
            "bipolar": "bipolar.json",
            "schizophrenia": "schizophrenia.json",
            "adhd": "adhd.json",
            "ocd": "ocd.json",
            "panic": "anxiety.json", # 예시
            "substance": "substance.json"
        }
        
        filename = mapping.get(disease_key)
        if not filename:
            # 파일명 직접 매칭 시도
            filename = f"{disease_key}.json"
            
        loaded_context = load_context_from_file(f"diseases/{filename}")
        if loaded_context:
            disease_context = loaded_context
        else:
            # 파일을 못 찾은 경우: 일반적인 심각도 평가 가이드 사용
            disease_context = "(해당 질환의 특화된 심각도 척도 파일이 없어, 일반적인 증상 강도와 빈도를 기준으로 평가합니다.)"
            
    except Exception as e:
        print(f"심각도 컨텍스트 로드 오류: {e}")
        disease_context = "(심각도 컨텍스트 로드 실패)"

    # 3. 프롬프트 로드
    prompt_path = Path("prompts/stage4_severity.md")
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            base_prompt = "기본 프롬프트 로드 실패"
    except Exception as e:
        base_prompt = f"프롬프트 로드 오류: {e}"
        
    # 4. 공통 Severity Context 로드
    common_severity_context = load_context_from_file("stage_specific/context_stage4_severity.json")

    # 5. 시스템 지시사항 구성
    system_instructions = f"""
{base_prompt}

## 평가 대상 질환: {target_diagnosis}

## 질환별 심각도 척도 정보
{disease_context}

## 공통 가이드라인
{common_severity_context}

## 수행 지침
1. **질문 단계**: 심각도 평가에 필요한 질문을 사용자에게 던지세요. (이미 파악된 정보가 있다면 중복 질문을 피하고 심화 질문을 하세요.)
2. **평가 완료 단계**: 충분한 정보가 모였다면, 심각도 평가 결과를 도출하고 아래 형식으로 출력하세요.

## 출력 제어
- 질문 진행 중일 때는 사용자에게 자연스럽게 대화하세요.
- 평가가 완료되면, 반드시 `---INTERNAL_DATA---` 섹션에 결과를 출력하세요.

---INTERNAL_DATA---
Severity Result String: [심각도 평가 결과 텍스트 요약]
Severity JSON: {{"diagnosis": "{target_diagnosis}", "level": "...", "score": "..."}}
"""

    # 6. LLM 호출
    # ask_openai 사용 (히스토리 포함)
    history = [{"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content} for m in messages]
    previous_history = history[:-1] if history else []
    
    response_text = ask_openai(
        user_input=user_input if user_input else f"{target_diagnosis}에 대한 심각도 평가를 시작합니다.",
        context=system_instructions, # context 인자에 시스템 프롬프트 전체를 넘김
        conversation_history=previous_history
    )
    
    # 7. 응답 파싱 및 State 업데이트
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
        
    if "Severity Result String:" in internal_data:
        result_string = internal_data.split("Severity Result String:")[1].split("Severity JSON:")[0].strip()
        new_state["severity_result_string"] = result_string
        
        # JSON 파싱은 선택 사항 (State에 구조화된 데이터 저장 시)
        # if "Severity JSON:" in internal_data: ...
        
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }

