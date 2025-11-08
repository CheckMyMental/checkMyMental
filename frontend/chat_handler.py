# 채팅 히스토리 관리 및 메시지 처리 모듈
import streamlit as st
import re
from .gemini_api import ask_gemini, ask_gemini_with_stage
from .stage_handler import StageHandler


def remove_system_tags(response: str) -> str:
    """
    시스템 내부 처리용 태그를 제거하여 사용자에게 표시할 내용만 반환
    - Summary String:
    - Hypothesis String:
    - Validated String:
    - Final Response String:
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
    
    # Assistant 메시지 형식으로 포맷팅 (각 섹션 사이에 빈 줄 추가)
    message = f"""**{guideline['title']}**

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
    
    # 초기 가이드라인 메시지 추가 (첫 실행 시에만)
    if "guideline_added" not in st.session_state:
        current_stage = st.session_state.stage_handler.get_current_stage()
        guideline_message = get_stage_guideline_message(current_stage)
        if guideline_message:
            st.session_state.messages.append({
                "role": "assistant",
                "content": guideline_message
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
    
    # 시스템 태그 제거 후 AI 응답 추가
    cleaned_response = remove_system_tags(response)
    print(f"[Chat Handler] 태그 제거 후 응답 길이: {len(cleaned_response)} 문자")
    
    add_assistant_message(cleaned_response)
    
    # 자동 단계 전환 체크
    # 원본 response를 사용하여 태그 확인 (cleaned_response가 아닌)
    # conversation_history를 전달하여 Stage 1의 경우 추가 검증 수행
    current_history = get_conversation_history(exclude_last=False)  # 현재까지의 전체 히스토리
    if stage_handler.should_transition(response, conversation_history=current_history):
        stage_handler.move_to_next_stage()
        
        # 다음 단계의 가이드라인 메시지 추가
        next_stage = stage_handler.get_current_stage()
        guideline_message = get_stage_guideline_message(next_stage)
        if guideline_message:
            add_assistant_message(guideline_message)
    
    return cleaned_response


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

