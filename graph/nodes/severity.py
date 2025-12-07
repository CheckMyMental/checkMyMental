import json
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_gemini
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
    print(f"[Severity Node] 현재 상태 확인:")
    print(f"  - severity_diagnosis: {target_diagnosis}")
    print(f"  - severity_result_string: {state.get('severity_result_string')}")
    print(f"  - is_re_intake: {state.get('is_re_intake')}")
    
    if not target_diagnosis:
        error_msg = "오류: 심각도 평가 대상 질환이 설정되지 않았습니다."
        print(f"[Severity Node] ✗ {error_msg}")
        return {"messages": [AIMessage(content=error_msg)]}
    
    # 이미 심각도 평가가 완료되었으면 더 이상 질문하지 않고 빈 상태 반환 (edges.py에서 자동 분기)
    existing_result = state.get("severity_result_string")
    if existing_result:
        print("[Severity Node] ⚠️ 이미 심각도 평가 완료됨 - 더 이상 질문 생성하지 않음, edges.py에서 자동 분기")
        print(f"[Severity Node] → Solution 단계로 자동 이동 예정")
        # 빈 상태 반환하여 edges.py에서 자동으로 다음 단계로 분기하도록 함
        return {}
    
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
2. **평가 완료 단계 (매우 중요!)**: 충분한 정보가 모였다면, 즉시 심각도 평가 결과를 도출하고 아래 형식으로 출력하세요.
   - **평가 완료 후에는 절대로 더 이상 질문하지 마세요!**
   - 평가 결과를 생성하면 자동으로 5단계(solution)로 넘어갑니다.

## 출력 제어
- 질문 진행 중일 때는 사용자에게 자연스럽게 대화하세요.
- **평가가 완료되면, 반드시 `---INTERNAL_DATA---` 섹션에 결과를 출력하고 더 이상 질문하지 마세요!**

---INTERNAL_DATA---
Severity Result String: [심각도 평가 결과 텍스트 요약]
Severity JSON: {{"diagnosis": "{target_diagnosis}", "level": "...", "score": "..."}}

**중요**: Severity Result String이 생성되면 평가가 완료된 것이며, 자동으로 Solution 단계로 넘어갑니다. 더 이상 질문하지 마세요!
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
    
    # 심각도 평가가 충분히 진행되었는지 확인 (validation 단계와 유사한 로직)
    # Severity 단계에서 질문-답변이 여러 번 진행되었다면 강제로 결과 생성 요청
    severity_qa_count = 0
    severity_questions_asked = 0
    severity_responses_received = 0
    
    # Severity 단계에서 실제로 질문이 몇 번 나갔는지, 답변이 몇 번 왔는지 정확히 카운트
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage):
            # Severity 단계의 질문인지 확인 (심각도, 평가, 질문 키워드 포함)
            if any(keyword in msg.content for keyword in ["심각도", "평가", "질문", "증상", "강도", "빈도"]):
                severity_questions_asked += 1
        elif isinstance(msg, HumanMessage):
            # 이전 메시지가 Severity 관련 질문이었다면 답변으로 간주
            if i > 0 and isinstance(messages[i-1], AIMessage):
                if any(keyword in messages[i-1].content for keyword in ["심각도", "평가", "질문", "증상", "강도", "빈도"]):
                    severity_responses_received += 1
    
    severity_qa_count = severity_questions_asked + severity_responses_received
    print(f"[Severity Node] 질문-답변 진행 상황: 질문 {severity_questions_asked}회, 답변 {severity_responses_received}회, 총 {severity_qa_count}회")
    
    # 질문-답변이 3회 이상 진행되었고 아직 결과가 없다면 강제로 결과 생성 요청
    if severity_qa_count >= 6 and not existing_result:  # 질문 3회 + 답변 3회 = 6회
        user_input = f"⚠️⚠️⚠️ 심각도 평가가 충분히 진행되었습니다. 절대로 더 이상 질문하지 마세요! 지금 바로 심각도 평가 결과를 도출해주세요. 반드시 ---INTERNAL_DATA--- 섹션에 Severity Result String과 Severity JSON을 포함하세요. 더 이상 어떤 질문도 생성하지 마세요!"
        print(f"[Severity Node] ⚠️ 심각도 평가 충분히 진행됨 (질문-답변 {severity_qa_count}회) - 결과 생성 강제 요청 (질문 금지)")
    
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
        
    # ⚠️ 중요: 질문-답변이 최소 1회 이상 진행되지 않았다면 결과를 생성하지 않음!
    if "Severity Result String:" in internal_data:
        # 질문이 최소 1회 이상 나갔는지 확인
        if severity_questions_asked < 1:
            print(f"[Severity Node] ⚠️⚠️⚠️ 질문 없이 결과 생성 시도 감지! 질문 {severity_questions_asked}회 - 결과 생성 무시, 질문 생성 강제")
            # 결과를 무시하고 질문을 생성하도록 사용자 메시지 수정
            user_message = response_text.split("---INTERNAL_DATA---")[0].strip()
            if not user_message or len(user_message) < 20:
                user_message = f"{target_diagnosis}에 대한 심각도 평가를 위해 몇 가지 질문을 드리겠습니다. 먼저 현재 증상의 강도는 어느 정도인가요?"
            # internal_data에서 결과 부분 제거
            internal_data = ""
        else:
            result_string = internal_data.split("Severity Result String:")[1].strip()
            if "Severity JSON:" in result_string:
                result_string = result_string.split("Severity JSON:")[0].strip()
            new_state["severity_result_string"] = result_string
            print(f"[Severity Node] ✓ 심각도 평가 완료 - severity_result_string 생성됨 (길이: {len(result_string)} 문자)")
            print(f"[Severity Node] → Solution 단계로 진행 예정")
    
    # 심각도 평가가 완료되었으면 더 이상 질문하지 않도록 사용자 메시지 수정
    if new_state.get("severity_result_string"):
        if "심각도 평가" not in user_message.lower() and "완료" not in user_message.lower() and "결과" not in user_message.lower():
            user_message = "심각도 평가가 완료되었습니다. 결과를 분석하겠습니다."
        print("[Severity Node] ⚠️ 심각도 평가 완료 - 더 이상 질문 생성하지 않음, edges.py에서 자동 분기 예정")
        
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }

