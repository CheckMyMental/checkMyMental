import json
import re
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file

def validation_node(state: CounselingState) -> Dict[str, Any]:
    """
    Validation Stage (3단계) 처리 노드
    - 의심 질환 검증을 위한 5지선다 질문 생성 및 응답 수집
    - 1턴: 질문 생성 (질환 기준 기반)
    - 2턴~: 사용자 응답 수집 및 진행
    - 마지막: 모든 답변 수집 후 확률 계산 및 결과 도출
    """
    
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
    
    # 프롬프트 로드
    prompt_path = Path("prompts/stage3_validation.md")
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            base_prompt = "기본 프롬프트 로드 실패"
    except Exception as e:
        base_prompt = f"프롬프트 로드 오류: {e}"

    # Context 로드
    validation_context = load_context_from_file("stage_specific/context_stage3_validation.json")
    
    # 시스템 지시사항 구성
    # 상황에 따라 프롬프트를 다르게 구성 (질문 생성 vs 결과 분석)
    
    # 이미 질문이 진행 중인지 확인 (메시지 히스토리 분석)
    # 간단히: 이전 AI 메시지에 "questions_generated": true 표식이 있는지 등으로 판단 가능.
    # 하지만 LLM에게 현재 대화 맥락을 주고 판단하게 하는 것이 가장 유연함.
    
    system_instructions = f"""
{base_prompt}

## 현재 상담 진행 상황
- **의심 질환 및 기준**:
{json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)}

## Validation 단계 처리 지침
1. **(질문 생성)**: 아직 질문 리스트가 생성되지 않았다면, 위 의심 질환들을 검증하기 위한 질문 리스트(JSON)를 생성하고 첫 번째 질문을 사용자에게 던지세요.
2. **(응답 수집)**: 사용자가 답변을 하면, 다음 질문을 이어서 하세요.
3. **(결과 분석)**: 모든 질문에 대한 답변이 수집되었다면, 각 질환별 확률을 계산하고 결과를 도출하세요.

## 출력 제어
- **질문 진행 중**: 사용자에게는 한 번에 하나의 질문만 하세요. (5지선다 옵션 포함)
- **완료 시**: 
    - `Validated String:` 태그 뒤에 최종 확정된 질환명(Top 1)을 적으세요. (확률 50% 미만이면 "None" 표기)
    - `Validation JSON:` 태그 뒤에 각 질환별 계산된 확률 정보를 JSON으로 출력하세요.
    
## Internal Data Format
---INTERNAL_DATA---
Validated String: [질환명 or None]
Validation JSON: {"질환A": 0.7, "질환B": 0.4, ...}
"""

    # LLM 호출
    full_context = f"{system_instructions}\n\n## Context Data\n{validation_context}"
    
    # 히스토리 처리 (ask_openai 사용)
    # 이전 대화 맥락이 있어야 질문 순서를 기억함
    history = [{"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content} for m in messages]
    previous_history = history[:-1] if history else [] # 현재 user_input 제외
    
    response_text = ask_openai(
        user_input=user_input if user_input else "Validation 단계를 시작합니다. 질문을 생성해주세요.",
        context=full_context,
        conversation_history=previous_history
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

