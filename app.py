"""
AI 상담 프로토타입 메인 애플리케이션
"""
import streamlit as st
from frontend.config import check_api_key
from frontend.ui_components import (
    setup_page_config,
    render_sidebar,
    render_main_header,
    render_chat_messages,
    render_user_input,
)
from frontend.chat_handler import init_chat_history, process_user_input

# API 키 확인
check_api_key()

# 페이지 설정
setup_page_config()

# 사이드바 렌더링
render_sidebar()

# 메인 헤더 렌더링
render_main_header()

# 채팅 히스토리 초기화
init_chat_history()

# 채팅 메시지 표시
render_chat_messages(st.session_state.messages)

# 사용자 입력 처리
user_input = render_user_input()

if user_input:
    # 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # AI 응답 생성 및 표시
    # process_user_input 내부에서 이미 시스템 태그가 제거된 응답을 반환함
    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하는 중..."):
            response = process_user_input(user_input)
            st.markdown(response)
