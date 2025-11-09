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
        # UI 컴포넌트 방식으로 가이드라인을 렌더링하므로, 채팅 메시지로는 인사만 남김
        greeting_message = "안녕하세요! 저는 AI 정신건강 상담 도우미입니다. 오늘 어떤 도움이 필요하신가요? 편하게 말씀해주세요."
        st.session_state.messages.append({
            "role": "assistant",
            "content": greeting_message,
            "is_guideline": False
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


def execute_stage_initial_action(stage: int):
    """
    단계 전환 후 초기 행동 자동 실행
    
    Args:
        stage: 전환된 새로운 단계 번호
    """
    stage_handler = st.session_state.stage_handler
    behavior = stage_handler.get_stage_behavior(stage)
    
    # 단계별 가이드라인 UI 컴포넌트 렌더링
    try:
        from .ui_components import render_stage_guideline_by_stage
        render_stage_guideline_by_stage(stage)
    except Exception as e:
        print(f"[Stage {stage}] 가이드라인 UI 렌더 실패: {e}")
    
    print(f"[Stage {stage}] 초기 행동 실행 시작 (behavior: {behavior})")
    
    if stage == 2:
        # Stage 2: 가설 생성 (완전 자동)
        execute_stage2_hypothesis_generation()
    elif stage == 3:
        # Stage 3: 감별 질문 생성 (자동)
        execute_stage3_initial_question()
    elif stage == 4:
        # Stage 4: 최종 요약 생성 (자동)
        execute_stage4_final_summary()
    # Stage 1은 사용자 입력 대기 (가이드라인 메시지만 표시)


def execute_stage2_hypothesis_generation():
    """
    Stage 2: 가설 생성 단계 자동 실행
    사용자 입력 없이 Summary String -> Hypothesis String 생성
    """
    print(f"[Stage 2] 자동 가설 생성 시작")
    
    # Stage 2 가이드라인 UI 컴포넌트 표시
    try:
        from .ui_components import render_stage_guideline_by_stage
        render_stage_guideline_by_stage(2)
    except Exception as e:
        print(f"[Stage 2] 가이드라인 UI 렌더 실패: {e}")
    
    stage_handler = st.session_state.stage_handler
    
    # Stage 1의 Summary String 가져오기
    stage1_output = stage_handler.get_stage_output(1)
    if not stage1_output:
        print(f"[Stage 2 오류] Stage 1 데이터 없음")
        add_assistant_message("오류: 이전 단계의 데이터를 찾을 수 없습니다.")
        return
    
    summary_report = stage1_output.get("summary_report", "")
    
    # 사용자에게 처리 중임을 알림
    processing_message = "수집하신 정보를 바탕으로 관련 질환을 검색하고 있습니다. 잠시만 기다려주세요..."
    add_assistant_message(processing_message)
    
    # Stage 2 프롬프트와 컨텍스트 로드
    prompt_template, context_data = stage_handler.get_stage_materials(2)
    
    # Gemini API 호출 (user_input은 비어있음 - 이전 단계 데이터만 사용)
    response = ask_gemini_with_stage(
        user_input="",  # Stage 2는 사용자 입력 불필요
        prompt_template=prompt_template,
        context_data=context_data,
        conversation_history=None,  # Stage 2는 히스토리 불필요
        previous_stage_data=stage1_output
    )
    
    # 응답 검증
    if not response or response.strip() == "":
        print(f"[Stage 2 오류] 빈 응답이 반환되었습니다!")
        add_assistant_message("가설 생성 중 오류가 발생했습니다. 다시 시도해주세요.")
        return
    
    # 응답 파싱
    user_message, internal_data = parse_ai_response(response)
    
    # 내부 데이터 확인 및 저장
    transition_data = internal_data if internal_data else response
    
    if "Hypothesis String:" in transition_data:
        # Hypothesis String 저장
        stage_handler.save_stage_output(2, {
            "hypothesis_report": transition_data
        })
        
        print(f"[Stage 2] 가설 생성 완료 - Stage 3으로 자동 전환")
        
        # Stage 3로 자동 전환
        stage_handler.move_to_next_stage()
        
        # Stage 3 가이드라인 UI 컴포넌트 표시
        try:
            from .ui_components import render_stage_guideline_by_stage
            render_stage_guideline_by_stage(3)
        except Exception as e:
            print(f"[Stage 3] 가이드라인 UI 렌더 실패: {e}")
        
        # Stage 3 초기 행동 실행 (감별 질문 생성)
        execute_stage3_initial_question()
    else:
        print(f"[Stage 2 오류] Hypothesis String 생성 실패")
        add_assistant_message("가설 생성 중 오류가 발생했습니다. 다시 시도해주세요.")


def execute_stage3_initial_question():
    """
    Stage 3: 감별 질문 자동 생성 및 제시
    Hypothesis String -> 감별 질문 생성
    """
    print(f"[Stage 3] 감별 질문 생성 시작")
    
    # Stage 3 가이드라인 UI 컴포넌트 표시
    try:
        from .ui_components import render_stage_guideline_by_stage
        render_stage_guideline_by_stage(3)
    except Exception as e:
        print(f"[Stage 3] 가이드라인 UI 렌더 실패: {e}")
    
    stage_handler = st.session_state.stage_handler
    
    # Stage 2의 Hypothesis String 가져오기
    stage2_output = stage_handler.get_stage_output(2)
    if not stage2_output:
        print(f"[Stage 3 오류] Stage 2 데이터 없음")
        add_assistant_message("오류: 가설 데이터를 찾을 수 없습니다.")
        return
    
    # Stage 3 프롬프트와 컨텍스트 로드
    prompt_template, context_data = stage_handler.get_stage_materials(3)
    
    # 감별 질문 생성 (첫 번째 호출)
    response = ask_gemini_with_stage(
        user_input="감별 질문을 생성해주세요.",  # 질문 생성 트리거
        prompt_template=prompt_template,
        context_data=context_data,
        conversation_history=get_conversation_history(),
        previous_stage_data=stage2_output
    )
    
    # 응답 검증
    if not response or response.strip() == "":
        print(f"[Stage 3 오류] 빈 응답이 반환되었습니다!")
        add_assistant_message("감별 질문 생성 중 오류가 발생했습니다.")
        return
    
    # 사용자에게 감별 질문 표시
    user_message, internal_data = parse_ai_response(response)
    if user_message:
        add_assistant_message(user_message)
        print(f"[Stage 3] 감별 질문 생성 완료 - 사용자 응답 대기")
    else:
        print(f"[Stage 3 오류] 감별 질문 생성 실패")


def execute_stage4_final_summary():
    """
    Stage 4: 최종 요약 및 솔루션 자동 생성
    Validated String + Stage 1 Summary -> Final Response
    """
    print(f"[Stage 4] 최종 요약 생성 시작")
    
    # Stage 4 가이드라인 UI 컴포넌트 표시
    try:
        from .ui_components import render_stage_guideline_by_stage
        render_stage_guideline_by_stage(4)
    except Exception as e:
        print(f"[Stage 4] 가이드라인 UI 렌더 실패: {e}")
    
    stage_handler = st.session_state.stage_handler
    
    # Stage 1과 Stage 3 데이터 가져오기
    stage1_output = stage_handler.get_stage_output(1)
    stage3_output = stage_handler.get_stage_output(3)
    
    if not stage1_output or not stage3_output:
        print(f"[Stage 4 오류] 이전 단계 데이터 없음")
        add_assistant_message("오류: 이전 단계의 데이터를 찾을 수 없습니다.")
        return
    
    # 사용자에게 처리 중임을 알림
    processing_message = "최종 분석 결과와 맞춤형 솔루션을 준비하고 있습니다..."
    add_assistant_message(processing_message)
    
    # Stage 4 프롬프트와 컨텍스트 로드
    prompt_template, context_data = stage_handler.get_stage_materials(4)
    
    # 통합 데이터 준비
    previous_stage_data = {
        "stage1_summary": stage1_output.get("summary_report", ""),
        "stage3_validation": stage3_output.get("validation_result", "")
    }
    
    # 최종 요약 생성
    response = ask_gemini_with_stage(
        user_input="",  # Stage 4는 사용자 입력 불필요
        prompt_template=prompt_template,
        context_data=context_data,
        conversation_history=get_conversation_history(),
        previous_stage_data=previous_stage_data
    )
    
    # 응답 검증
    if not response or response.strip() == "":
        print(f"[Stage 4 오류] 빈 응답이 반환되었습니다!")
        add_assistant_message("최종 요약 생성 중 오류가 발생했습니다.")
        return
    
    # 최종 응답 파싱 및 표시
    user_message, internal_data = parse_ai_response(response)
    if user_message:
        add_assistant_message(user_message)
        print(f"[Stage 4] 최종 요약 생성 완료")
        
        # 추가 질문 안내
        add_assistant_message("추가로 궁금하신 점이 있으시면 언제든 말씀해주세요.")
    else:
        print(f"[Stage 4 오류] 최종 요약 생성 실패")


# 사용자 입력을 처리하고 AI 응답 생성
# 현재 단계에 맞는 프롬프트와 컨텍스트를 사용
def process_user_input(user_input):

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
        
        # 다음 단계로 이동
        stage_handler.move_to_next_stage()
        next_stage = stage_handler.get_current_stage()
        
        # 다음 단계의 가이드라인은 별도의 UI 컴포넌트로 렌더링됨 (채팅 메시지로 추가하지 않음)
        
        # ★★★ 핵심: 다음 단계의 초기 행동 자동 실행 ★★★
        execute_stage_initial_action(next_stage)
    
    return user_message if user_message else "분석 중입니다..."

# 현재 단계 정보 반환
def get_current_stage_info():
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

