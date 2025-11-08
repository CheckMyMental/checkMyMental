# UI 컴포넌트 모듈
import streamlit as st


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
        ("1️⃣", "초기 접수 (Intake)", "증상과 감정을 수집합니다"),
        ("2️⃣", "가설 생성 (Hypothesis Generation)", "관련 질환을 검색 중입니다"),
        ("3️⃣", "진단 검증 (Validation)", "질환을 감별하고 확정합니다"),
        ("4️⃣", "솔루션 및 요약 (Solution & Summary)", "최종 요약과 행동 계획을 제시합니다")
    ]
    
    current_stage = stage_info["stage"] if stage_info else 1
    
    for idx, (emoji, name, desc) in enumerate(stages, 1):
        if idx == current_stage:
            # 현재 단계는 강조 표시
            st.sidebar.markdown(f"**{emoji} {name}** ⬅️ 현재")
            st.sidebar.markdown(f"   {desc}")
        elif idx < current_stage:
            # 완료된 단계
            st.sidebar.markdown(f"✅ {emoji} {name}")
        else:
            # 아직 진행하지 않은 단계
            st.sidebar.markdown(f"{emoji} {name}")
            st.sidebar.markdown(f"   {desc}")
    
    st.sidebar.markdown("---")
    
    # 단계 리셋 버튼 (개발/테스트용)
    if st.sidebar.button("🔄 단계 리셋"):
        if "stage_handler" in st.session_state:
            st.session_state.stage_handler.reset_stage()
            st.session_state.messages = []
            st.rerun()


def render_main_header():
    # 메인 헤더 표시
    st.title("💬 AI 정신건강 상담 도우미")
    st.markdown("---")


def render_chat_messages(messages):
    # 채팅 메시지들을 화면에 표시
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_user_input():
    # 사용자 입력창 표시
    return st.chat_input("지금 어떤 기분이신가요?")


def render_assistant_response(response):
    # AI 응답을 화면에 표시
    with st.chat_message("assistant"):
        st.markdown(response)

