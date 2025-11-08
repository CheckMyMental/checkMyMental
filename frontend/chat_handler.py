# 채팅 히스토리 관리 및 메시지 처리 모듈
import streamlit as st
from .gemini_api import ask_gemini, ask_gemini_with_stage
from .stage_handler import StageHandler


def init_chat_history():
    # 채팅 히스토리 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # StageHandler 초기화
    if "stage_handler" not in st.session_state:
        st.session_state.stage_handler = StageHandler()


def add_user_message(content):
    # 사용자 메시지를 히스토리에 추가
    st.session_state.messages.append({"role": "user", "content": content})


def add_assistant_message(content):
    # AI 응답을 히스토리에 추가
    st.session_state.messages.append({"role": "assistant", "content": content})


def get_conversation_history(exclude_last=False):
    # 대화 히스토리 가져오기
    if exclude_last and len(st.session_state.messages) > 1:
        return st.session_state.messages[:-1]
    return st.session_state.messages.copy()


def process_user_input(user_input):
    """
    사용자 입력을 처리하고 AI 응답 생성
    현재 단계에 맞는 프롬프트와 컨텍스트를 사용
    """
    add_user_message(user_input)
    
    # StageHandler 가져오기
    stage_handler = st.session_state.stage_handler
    current_stage = stage_handler.get_current_stage()
    print(f"--------------------------------")
    print(f"사용자 입력: {user_input}")
    print(f"현재 단계: {current_stage} ({stage_handler.get_stage_name()})")
    print(f"--------------------------------")
    
    # 현재 단계의 프롬프트와 컨텍스트 로드
    prompt_template, context_data = stage_handler.get_stage_materials()
    
    # 대화 히스토리 가져오기 (현재 메시지 제외)
    history = get_conversation_history(exclude_last=True)
    
    # 이전 단계 데이터 가져오기
    previous_stage_data = None
    if current_stage > 1:
        # Stage 4는 Stage 1과 Stage 3의 데이터가 모두 필요
        if current_stage == 4:
            stage1_data = stage_handler.get_stage_output(1)
            stage3_data = stage_handler.get_stage_output(3)
            # 두 단계의 데이터를 통합
            previous_stage_data = {
                "stage1_summary": stage1_data.get("summary_report", "") if stage1_data else "",
                "stage3_validation": stage3_data.get("validation_result", "") if stage3_data else ""
            }
            # print(f"[Stage 4] 이전 단계 데이터:")
            # print(f"  - Stage 1 Summary 길이: {len(previous_stage_data['stage1_summary'])}자")
            # print(f"  - Stage 3 Validation 길이: {len(previous_stage_data['stage3_validation'])}자")
        else:
            # 다른 단계는 바로 이전 단계의 데이터만 필요
            previous_stage_data = stage_handler.get_stage_output(current_stage - 1)
            if previous_stage_data:
                print(f"[Stage {current_stage}] 이전 단계 (Stage {current_stage - 1}) 데이터:")
                for key, value in previous_stage_data.items():
                    if isinstance(value, str):
                        print(f"  - {key}: {len(value)}자")
                    else:
                        print(f"  - {key}: {type(value)}")
            else:
                print(f"[Stage {current_stage}] 이전 단계 데이터 없음")
    else:
        print(f"[Stage {current_stage}] 이전 단계 데이터 없음 (첫 번째 단계)")
    
    print(f"{'*'*80}\n")
    
    # 단계별 Gemini API 호출
    response = ask_gemini_with_stage(
        user_input=user_input,
        prompt_template=prompt_template,
        context_data=context_data,
        conversation_history=history,
        previous_stage_data=previous_stage_data
    )
    
    # AI 응답 추가
    add_assistant_message(response)
    
    # 자동 단계 전환 체크 (예: Stage 1에서 JSON 출력 시)
    if stage_handler.should_transition(response):
        stage_handler.move_to_next_stage()
        # 단계 전환 알림 메시지 추가 (선택적)
        transition_msg = f"[시스템] Stage {current_stage} 완료. Stage {current_stage + 1}로 진행합니다."
        add_assistant_message(transition_msg)
    
    return response


def get_current_stage_info():
    """현재 단계 정보 반환"""
    if "stage_handler" not in st.session_state:
        return None
    
    stage_handler = st.session_state.stage_handler
    current_stage = stage_handler.get_current_stage()
    stage_name = stage_handler.get_stage_name()
    
    return {
        "stage": current_stage,
        "name": stage_name,
        "total_stages": 4
    }

