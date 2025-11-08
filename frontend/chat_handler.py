# 채팅 히스토리 관리 및 메시지 처리 모듈
import streamlit as st
import re
from .gemini_api import ask_gemini, ask_gemini_with_stage
from .stage_handler import StageHandler


def parse_ai_response(response: str) -> tuple:
    """
    AI 응답을 사용자 표시 부분과 내부 데이터로 분리
    
    응답 형식:
    [사용자에게 보여질 응답]
    
    ---INTERNAL_DATA---
    Summary String:
    [다음 단계로 전달될 구조화된 데이터]
    
    Returns:
        (user_message, internal_data)
        - user_message: 사용자에게 표시할 메시지
        - internal_data: 다음 단계로 전달할 내부 데이터 (Summary String 등)
    """
    # ---INTERNAL_DATA--- 구분자로 분리
    if "---INTERNAL_DATA---" in response:
        parts = response.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip() if len(parts) > 1 else ""
        
        print(f"[응답 파싱] 사용자 메시지: {len(user_message)} 문자")
        print(f"[응답 파싱] 내부 데이터: {len(internal_data)} 문자")
        
        return user_message, internal_data
    
    # 구분자가 없으면 전체를 사용자 메시지로 처리
    # (Summary String 등이 없는 일반 대화 응답)
    return response.strip(), ""


def remove_system_tags(response: str) -> str:
    """
    시스템 내부 처리용 태그를 제거하여 사용자에게 표시할 내용만 반환
    (레거시 함수 - parse_ai_response 사용 권장)
    """
    # 각 태그 패턴을 찾아서 태그와 콜론만 제거 (내용은 유지)
    patterns = [
        r'Summary String:\s*',
        r'Hypothesis String:\s*',
        r'Validated String:\s*',
        r'Final Response String:\s*',
    ]
    
    cleaned = response
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # 앞뒤 공백 제거
    return cleaned.strip()


def get_stage_guideline_message(stage: int) -> str:
    """단계별 가이드라인을 Assistant 메시지 형식으로 반환"""
    from .stage_guidelines import STAGE_GUIDELINES
    
    guideline = STAGE_GUIDELINES.get(stage)
    if not guideline:
        return ""
    
    # 할 일 목록 생성 (마크다운 리스트 형식으로, 각 항목 사이에 빈 줄 추가)
    what_to_do_list = "\n".join([f"- {item}" for item in guideline['what_to_do']])
    tips_list = "\n".join([f"- {item}" for item in guideline['tips']])
    
    # Assistant 메시지 형식으로 포맷팅 (title은 HTML로 처리하여 크기 조정)
    # 이모지와 함께 제대로 표시되도록 HTML 사용
    message = f"""<h3 style="margin-top: 0; margin-bottom: 0.5rem; font-size: 1.3em;">{guideline['title']}</h3>

{guideline['description']}

**이 단계에서 할 일:**

{what_to_do_list}

**💡 유의사항:**

{tips_list}
"""
    return message


def init_chat_history():
    # 채팅 히스토리 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # StageHandler 초기화
    if "stage_handler" not in st.session_state:
        st.session_state.stage_handler = StageHandler()
    
    # 초기 가이드라인 메시지 및 인사 메시지 추가 (첫 실행 시에만)
    if "guideline_added" not in st.session_state:
        current_stage = st.session_state.stage_handler.get_current_stage()
        guideline_message = get_stage_guideline_message(current_stage)
        if guideline_message:
            # 가이드라인 메시지 추가
            st.session_state.messages.append({
                "role": "assistant",
                "content": guideline_message,
                "is_guideline": True,  # 가이드라인 메시지 플래그
                "stage": current_stage  # 단계 정보 저장
            })
            
            # 인사 메시지 추가
            greeting_message = "안녕하세요! 저는 AI 정신건강 상담 도우미입니다. 오늘 어떤 도움이 필요하신가요? 편하게 말씀해주세요."
            st.session_state.messages.append({
                "role": "assistant",
                "content": greeting_message,
                "is_guideline": False  # 일반 메시지
            })
            
            st.session_state.guideline_added = True


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
    
    # Stage 1인 경우 턴 수 증가 (사용자 응답이 들어왔으므로)
    if current_stage == 1:
        stage_handler.increment_stage1_turn()
        print(f"[Stage 1] 현재 대화 턴 수: {stage_handler.get_stage1_turn_count()}")
    
    # 단계별 Gemini API 호출
    response = ask_gemini_with_stage(
        user_input=user_input,
        prompt_template=prompt_template,
        context_data=context_data,
        conversation_history=history,
        previous_stage_data=previous_stage_data
    )
    
    # 응답 검증
    if not response or response.strip() == "":
        print(f"[오류] 빈 응답이 반환되었습니다!")
        response = "죄송합니다. 응답 생성에 문제가 발생했습니다. 다시 시도해주세요."
    
    print(f"[Chat Handler] 원본 응답 길이: {len(response)} 문자")
    
    # 응답을 사용자 메시지와 내부 데이터로 분리
    user_message, internal_data = parse_ai_response(response)
    
    # 사용자에게 표시할 메시지가 있으면 추가
    if user_message:
        add_assistant_message(user_message)
        print(f"[Chat Handler] 사용자에게 표시: {len(user_message)} 문자")
    else:
        print(f"[Chat Handler] 사용자에게 표시할 메시지 없음 (내부 처리 단계)")
    
    # 단계 전환 체크는 내부 데이터 또는 전체 응답 사용
    transition_data = internal_data if internal_data else response
    
    # 자동 단계 전환 체크
    current_history = get_conversation_history(exclude_last=False)
    if stage_handler.should_transition(transition_data, conversation_history=current_history):
        print(f"[Chat Handler] 단계 전환 조건 충족 - 내부 데이터 저장 중")
        
        # 내부 데이터를 stage_output에 저장 (다음 단계 입력으로 사용)
        if "Summary String:" in transition_data:
            stage_handler.save_stage_output(current_stage, {
                "summary_report": transition_data,
                "user_visible_message": user_message
            })
        elif "Hypothesis String:" in transition_data:
            stage_handler.save_stage_output(current_stage, {
                "hypothesis_report": transition_data
            })
        elif "Validated String:" in transition_data:
            stage_handler.save_stage_output(current_stage, {
                "validation_result": transition_data,
                "user_visible_message": user_message
            })
        
        stage_handler.move_to_next_stage()
        
        # 다음 단계의 가이드라인 메시지 추가
        next_stage = stage_handler.get_current_stage()
        guideline_message = get_stage_guideline_message(next_stage)
        if guideline_message:
            st.session_state.messages.append({
                "role": "assistant",
                "content": guideline_message,
                "is_guideline": True,
                "stage": next_stage
            })
    
    return user_message if user_message else "분석 중입니다..."


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

