# UI 컴포넌트 모듈
import streamlit as st
import time


def setup_page_config():
    # 페이지 설정
    st.set_page_config(
        page_title="AI 상담 프로토타입",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar():
    # 사이드바 - 상담 단계 표시
    st.sidebar.title("📋 상담 단계")

    # 현재 단계 정보 가져오기
    from .chat_handler import get_current_stage_info

    stage_info = get_current_stage_info()

    stages = [
        ("1.초기 접수 (Intake)", "증상과 감정을 수집합니다", "#2E5C8A"),
        ("2.가설 생성 (Hypothesis Generation)", "관련 질환을 검색 중입니다", "#2D8659"),
        ("3.진단 검증 (Validation)", "질환을 감별하고 확정합니다", "#CC6F35"),
        (
            "4.솔루션 및 요약 (Solution & Summary)",
            "최종 요약과 행동 계획을 제시합니다",
            "#7D3C98",
        ),
    ]
    current_stage = stage_info["stage"] if stage_info else 1

    for idx, (name, desc, name_color) in enumerate(stages, 1):
        if idx == current_stage:
            # 현재 단계는 글씨체를 키워서 강조하고 색상 적용
            st.sidebar.markdown(
                f'<p style="font-weight: bold; font-size: 1.2em; color: {name_color}; margin-bottom: 5px;">{name}</p>',
                unsafe_allow_html=True,
            )
            st.sidebar.markdown(
                f"   <span style='color: #666;'>{desc}</span>", unsafe_allow_html=True
            )
        elif idx < current_stage:
            # 완료된 단계는 회색 처리
            st.sidebar.markdown(
                f'<p style="font-weight: bold; color: #999; margin-bottom: 5px;">{name}</p>',
                unsafe_allow_html=True,
            )
        else:
            # 아직 진행하지 않은 단계는 회색 처리
            st.sidebar.markdown(
                f'<p style="font-weight: bold; color: #999; margin-bottom: 5px;">{name}</p>',
                unsafe_allow_html=True,
            )
            st.sidebar.markdown(
                f"   <span style='color: #999;'>{desc}</span>", unsafe_allow_html=True
            )

    st.sidebar.markdown("---")

    # 초기화(개발,테스트용) 버튼 (개발/테스트용)
    if st.sidebar.button("초기화(개발,테스트용)"):
        if "stage_handler" in st.session_state:
            st.session_state.stage_handler.reset_stage()
            st.session_state.messages = []
            # 가이드라인 메시지도 다시 추가되도록 플래그 초기화
            if "guideline_added" in st.session_state:
                del st.session_state.guideline_added
            # 렌더링 카운트도 초기화
            if "rendered_message_count" in st.session_state:
                del st.session_state.rendered_message_count
            st.rerun()


def render_main_header():
    # 메인 헤더 표시
    st.title("💬 AI 정신건강 상담 도우미")
    st.markdown("---")


def render_chat_messages(messages):
    # 이미 렌더링된 메시지 수 추적
    if "rendered_message_count" not in st.session_state:
        st.session_state.rendered_message_count = 0
    
    # 채팅 메시지들을 화면에 표시
    for idx, message in enumerate(messages):
        # 가이드라인 메시지인지 확인
        is_guideline = message.get("is_guideline", False)

        if is_guideline:
            # 가이드라인 메시지는 이미 HTML로 스타일링되어 있으므로 그대로 표시
            # content가 이미 완전한 HTML이므로 unsafe_allow_html=True 필요
            with st.chat_message(message["role"]):
                st.markdown(message["content"], unsafe_allow_html=True)
        else:
            # 일반 메시지 표시
            with st.chat_message(message["role"]):
                # 사용자 메시지는 바로 표시
                if message["role"] == "user":
                    st.markdown(message["content"])
                else:
                    # 새로 추가된 Assistant 메시지만 타이핑 효과 적용
                    # 이미 표시된 메시지는 바로 표시
                    if idx < st.session_state.rendered_message_count:
                        st.markdown(message["content"])
                    else:
                        # 새 메시지는 타이핑 효과 적용
                        _render_typing_effect(message["content"])
    
    # 렌더링된 메시지 수 업데이트
    st.session_state.rendered_message_count = len(messages)


def render_user_input():
    # 사용자 입력창 표시
    return st.chat_input("지금 어떤 기분이신가요?")


def _render_typing_effect(text, speed=0.02):
    """
    타이핑 효과로 텍스트를 표시
    
    Args:
        text: 표시할 텍스트
        speed: 각 문자 사이의 딜레이 (초)
    """
    # Streamlit의 write_stream을 사용 (1.28.0+)
    # 버전이 낮으면 fallback으로 일반 표시
    try:
        # 텍스트를 문자 단위로 나눠서 스트림으로 전달
        def text_generator():
            for char in text:
                yield char
                time.sleep(speed)
        
        st.write_stream(text_generator())
    except AttributeError:
        # write_stream이 없는 경우 일반 표시
        st.markdown(text)


def render_assistant_response(response):
    # AI 응답을 화면에 표시 (타이핑 효과 포함)
    with st.chat_message("assistant"):
        _render_typing_effect(response)


