import json
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.gemini_api import ask_gemini
from frontend.context_handler import load_context_from_file, load_prompt_from_file

def severity_node(state: CounselingState) -> Dict[str, Any]:
    """
    Severity Stage (4단계) 처리 노드
    - 확정된 1개 질환에 대한 심각도 평가 수행
    - 질환별 특화된 심각도 컨텍스트 로드 (있는 경우)
    - 질문 생성 및 응답 수집 루프
    - 최종 심각도 평가 결과 생성
    """
    print("=" * 60)
    print("[Stage 4: Severity] 노드 실행 시작")
    print("=" * 60)
    
    messages = state['messages']
    last_message = messages[-1] if messages else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 1. 확정된 질환명 확인
    target_diagnosis = state.get("severity_diagnosis")
    if not target_diagnosis:
        return {"messages": [AIMessage(content="오류: 심각도 평가 대상 질환이 설정되지 않았습니다.")]}
    
    # 2. 질환별 심각도 Context 동적 로드 시도
    # 예: "Depression" -> "contexts/diseases/depression.json"
    disease_context = ""
    try:
        # 질환명에서 핵심 단어 추출
        diagnosis_lower = target_diagnosis.lower()
        disease_key = diagnosis_lower.split()[0] if diagnosis_lower.split() else diagnosis_lower
        
        # 매핑 테이블 (질환명 -> 파일명)
        mapping = {
            "depressive": "depression.json",
            "depression": "depression.json",
            "major": "depression.json",  # Major Depressive Disorder
            "anxiety": "anxiety.json",
            "panic": "anxiety.json",
            "generalized": "anxiety.json",  # Generalized Anxiety Disorder
            "bipolar": "bipolar.json",
            "manic": "bipolar.json",
            "schizophrenia": "schizophrenia.json",
            "schizoaffective": "schizophrenia.json",
            "adhd": "adhd.json",
            "attention": "adhd.json",  # Attention-Deficit/Hyperactivity Disorder
            "ocd": "ocd.json",
            "obsessive": "ocd.json",  # Obsessive-Compulsive Disorder
            "substance": "substance.json",
            "alcohol": "substance.json",
            "drug": "substance.json"
        }
        
        # 매핑 테이블에서 찾기
        filename = None
        for key, mapped_file in mapping.items():
            if key in diagnosis_lower:
                filename = mapped_file
                break
        
        if not filename:
            # 직접 파일명 매칭 시도
            filename = f"{disease_key}.json"
            
        print(f"[Severity Node] 질환별 컨텍스트 로드 시도: diseases/{filename}")
        loaded_context = load_context_from_file(f"diseases/{filename}")
        if loaded_context:
            disease_context = loaded_context
            print(f"[Severity Node] ✓ 질환별 컨텍스트 로드 성공: {filename}")
        else:
            # 파일을 못 찾은 경우: 일반적인 심각도 평가 가이드 사용
            disease_context = "(해당 질환의 특화된 심각도 척도 파일이 없어, 일반적인 증상 강도와 빈도를 기준으로 평가합니다.)"
            print(f"[Severity Node] ⚠ 질환별 컨텍스트 파일을 찾을 수 없음: {filename}, 기본 가이드 사용")
            
    except Exception as e:
        print(f"[Severity Node] ✗ 심각도 컨텍스트 로드 오류: {e}")
        disease_context = "(심각도 컨텍스트 로드 실패)"

    # 3. 프롬프트 로드
    base_prompt = load_prompt_from_file("stage4_severity.md")
    if not base_prompt:
        base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        print(f"[Severity Node] ⚠ 프롬프트 파일 로드 실패: stage4_severity.md")
        
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
    # ask_gemini 사용 (히스토리 포함)
    # Severity 단계는 Validation 이후이므로, Validation 관련 메시지만 전달
    history = []
    for msg in messages[:-1]:  # 현재 메시지 제외
        if isinstance(msg, (HumanMessage, AIMessage)):
            # Severity 단계 관련 메시지 또는 최근 몇 개만
            if isinstance(msg, AIMessage) and ("Validation" in msg.content or "검증" in msg.content):
                # Validation 단계 이후의 메시지만 포함
                history.append({"role": "model", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                # 사용자 메시지는 최근 것만
                history.append({"role": "user", "content": msg.content})
    
    # Severity 관련 메시지가 없으면 최근 몇 개만 사용
    if not history:
        recent_messages = messages[-6:-1] if len(messages) > 1 else []
        history = [
            {"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content}
            for m in recent_messages
        ]
    else:
        # 최대 10개로 제한
        history = history[-10:]
    
    print(f"[Severity Node] 히스토리 메시지 수: {len(history)}개 (전체: {len(messages)}개)")
    
    response_text = ask_gemini(
        user_input=user_input if user_input else f"{target_diagnosis}에 대한 심각도 평가를 시작합니다.",
        context=system_instructions, # context 인자에 시스템 프롬프트 전체를 넘김
        conversation_history=history
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

