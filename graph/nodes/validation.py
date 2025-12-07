import json
import re
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.gemini_api import ask_gemini
from frontend.context_handler import load_context_from_file, load_prompt_from_file

def validation_node(state: CounselingState) -> Dict[str, Any]:
    """
    Validation Stage (3단계) 처리 노드
    - 의심 질환 검증을 위한 5지선다 질문 생성 및 응답 수집
    - 1턴: 질문 생성 (질환 기준 기반)
    - 2턴~: 사용자 응답 수집 및 진행
    - 마지막: 모든 답변 수집 후 확률 계산 및 결과 도출
    """
    print("=" * 60)
    print("[Stage 3: Validation] 노드 실행 시작")
    print("=" * 60)
    
    messages = state['messages']
    last_message = messages[-1] if messages else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 상태 정보 가져오기
    hypothesis_criteria = state.get("hypothesis_criteria", [])
    if not hypothesis_criteria:
         return {"messages": [AIMessage(content="오류: 가설 검증을 위한 기준 데이터가 없습니다. 상담을 초기화해주세요.")]}

    # 질문 리스트가 없으면 새로 생성해야 함 (첫 진입)
    # LangGraph State에는 질문 리스트를 저장할 명시적 필드가 없으므로, 
    # messages history나 임시 저장소를 활용해야 하지만,
    # 여기서는 '질문 생성 모드'와 '답변 처리 모드'를 user_input과 내부 데이터로 구분합니다.
    
    # 다만, 복잡한 상태(현재 몇 번째 질문인지 등)를 관리하려면
    # State에 `validation_state` 같은 Dict 필드를 추가하는 것이 좋으나,
    # 현재 정의된 State 내에서 처리하기 위해 메시지 히스토리의 'internal_data'를 활용하거나,
    # 한 번에 모든 질문을 생성하고 순차적으로 묻는 방식을 사용합니다.
    
    # 여기서는 구현 편의와 안정성을 위해:
    # 1. 첫 진입 시 모든 질문을 생성하여 JSON 형태로 반환받음.
    # 2. 이 질문 리스트를 프롬프트에 포함하여 매 턴마다 진행 상황을 추적하게 함.
    #    (State에 저장하지 않고 대화 맥락으로 유지)
    
    # 프롬프트 로드 (매번 새로 로드하여 최신 상태 유지)
    print(f"[Validation Node] 프롬프트 및 컨텍스트 파일 로드 시작...")
    base_prompt = load_prompt_from_file("stage3_validation.md")
    if not base_prompt:
        base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        print(f"[Validation Node] ⚠ 프롬프트 파일 로드 실패: stage3_validation.md")
    else:
        print(f"[Validation Node] ✓ 프롬프트 로드 완료: stage3_validation.md ({len(base_prompt)} 문자)")

    # Context 로드 (매번 새로 로드)
    validation_context = load_context_from_file("stage_specific/context_stage3_validation.json")
    if validation_context:
        print(f"[Validation Node] ✓ 컨텍스트 로드 완료: context_stage3_validation.json ({len(validation_context)} 문자)")
    else:
        print(f"[Validation Node] ⚠ 컨텍스트 로드 실패: context_stage3_validation.json")
    
    # 시스템 지시사항 구성
    # 상황에 따라 프롬프트를 다르게 구성 (질문 생성 vs 결과 분석)
    
    # 이미 질문이 진행 중인지 확인 (메시지 히스토리 분석)
    # 간단히: 이전 AI 메시지에 "questions_generated": true 표식이 있는지 등으로 판단 가능.
    # 하지만 LLM에게 현재 대화 맥락을 주고 판단하게 하는 것이 가장 유연함.
    
    # JSON 데이터를 먼저 문자열로 변환 (f-string 밖에서)
    criteria_json = json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)
    
    # 문자열 연결을 사용하여 JSON 중괄호 문제 완전히 방지
    # f-string을 사용 중이라면 아래와 같이 수정하세요
    # JSON 데이터 문자열 준비
    criteria_json_str = json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)

# 예시 JSON도 그냥 문자열
    validation_json_example = '{"질환A": 0.7, "질환B": 0.4}'

# ★ f-string 금지 — 그냥 문자열 이어붙이기
    system_instructions = (
    base_prompt
    + "\n\n## 현재 상담 진행 상황\n- **의심 질환 및 기준**:\n"
    + criteria_json_str
    + """

## Validation 단계 처리 지침
1. (질문 생성): 아직 질문 리스트가 생성되지 않았다면, 위 의심 질환들을 검증하기 위한 질문 리스트(JSON)를 생성하고 첫 번째 질문을 사용자에게 던지세요.
2. (응답 수집): 사용자가 답변을 하면, 다음 질문을 이어서 하세요.
3. (결과 분석): 모든 질문에 대한 답변이 수집되었다면, 각 질환별 확률을 계산하고 결과를 도출하세요.

## 출력 제어
- 질문 진행 중: 사용자에게는 한 번에 하나의 질문만 하세요. (5지선다 포함)
- 완료 시:
    - `Validated String:` 뒤에 최종 확정된 질환명 (없으면 None)
    - `Validation JSON:` 뒤에 각 질환별 확률 JSON 하나 출력

## Internal Data Format
Validated String: [질환명 또는 None]
Validation JSON: """
    + validation_json_example
)


    # LLM 호출 (f-string 대신 일반 문자열 연결 사용)
    full_context = system_instructions + "\n\n## Context Data\n" + validation_context
    
    # 히스토리 처리: Validation 단계에 필요한 메시지만 필터링
    # Validation 단계는 Hypothesis 이후에 시작되므로, Hypothesis 결과 이후의 메시지만 필요
    # 또는 Validation 관련 메시지만 추출
    history = []
    found_validation_start = False
    
    # 메시지를 역순으로 탐색하여 Validation 단계 시작점 찾기
    for msg in reversed(messages[:-1]):  # 현재 메시지 제외
        if isinstance(msg, AIMessage):
            # Hypothesis 단계의 결과 메시지 이후부터 Validation 메시지
            if "의심 질환" in msg.content or "질환 후보" in msg.content:
                found_validation_start = True
                break
            if found_validation_start or "Validation" in msg.content or "검증" in msg.content:
                history.insert(0, {"role": "model", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            if found_validation_start:
                history.insert(0, {"role": "user", "content": msg.content})
    
    # Validation 관련 메시지가 없으면 최근 몇 개만 사용 (너무 많은 히스토리 방지)
    if not history:
        recent_messages = messages[-6:-1] if len(messages) > 1 else []  # 최근 3쌍 (6개 메시지)
        history = [
            {"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content}
            for m in recent_messages
        ]
    else:
        # Validation 관련 메시지만 최근 10개로 제한
        history = history[-10:]
    
    print(f"[Validation Node] 히스토리 메시지 수: {len(history)}개 (전체: {len(messages)}개)")
    
    response_text = ask_gemini(
        user_input=user_input if user_input else "Validation 단계를 시작합니다. 질문을 생성해주세요.",
        context=full_context,
        conversation_history=history
    )
    
    # 응답 파싱
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
        
    # 결과 분석 (확률 및 재탐색 여부)
    if "Validation JSON:" in internal_data:
        try:
            json_str = internal_data.split("Validation JSON:")[1].strip()
            probabilities = json.loads(json_str)
            new_state["validation_probabilities"] = probabilities
            
            # 확률 체크 (모든 질환이 50% 이하인지)
            # 확률은 0.0 ~ 1.0 범위로 가정 (또는 백분율)
            # 여기서는 LLM이 어떻게 줄지 모르므로 0.5 또는 50 기준으로 유연하게 판단 필요하지만
            # 보통 0.0~1.0 스케일을 권장.
            
            max_prob = 0.0
            for prob in probabilities.values():
                if prob > max_prob:
                    max_prob = prob
            
            # 0.5 이하면 재탐색 (Re-Intake)
            if max_prob <= 0.5:
                new_state["is_re_intake"] = True
                new_state["severity_diagnosis"] = None # 진단 유보
            else:
                new_state["is_re_intake"] = False
                
        except Exception as e:
            print(f"Validation JSON 파싱 오류: {e}")
            
    if "Validated String:" in internal_data:
        diagnosis = internal_data.split("Validated String:")[1].strip()
        # "None"이 아니고 재탐색 모드가 아니면 진단명 설정
        if diagnosis.lower() != "none" and not new_state.get("is_re_intake", False):
             new_state["severity_diagnosis"] = diagnosis
        
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }

