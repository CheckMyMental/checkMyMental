# 채팅 히스토리 관리 및 메시지 처리 모듈
import streamlit as st
from .gemini_api import ask_gemini


def init_chat_history():
    # 채팅 히스토리 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []


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
    # 사용자 입력을 처리하고 AI 응답 생성
    add_user_message(user_input)
    
    # 대화 히스토리 가져오기 (현재 메시지 제외)
    history = get_conversation_history(exclude_last=True)
    
    # Gemini API 호출
    response = ask_gemini(user_input, conversation_history=history, context_file="stress_guide.md")
    
    # AI 응답 추가
    add_assistant_message(response)
    
    return response

