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
    st.sidebar.markdown(
        """
1️⃣ **관계 형성**  
   대화를 시작합니다

2️⃣ **증상 분류**  
   감정과 증상을 살펴봅니다

3️⃣ **검증**  
   내용을 분석 중입니다

4️⃣ **평가**  
   결과를 정리합니다

5️⃣ **솔루션**  
   개선 방향을 제시합니다
"""
    )


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

