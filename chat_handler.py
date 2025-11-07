"""
채팅 히스토리 관리 및 메시지 처리 모듈
"""
import streamlit as st
from gemini_api import ask_gemini


def init_chat_history():
    """채팅 히스토리 초기화"""
    if "messages" not in st.session_state:
        st.session_state.messages = []


def add_user_message(content):
    """
    사용자 메시지를 히스토리에 추가
    
    Args:
        content: 사용자 메시지 내용
    """
    st.session_state.messages.append({"role": "user", "content": content})


def add_assistant_message(content):
    """
    AI 응답을 히스토리에 추가
    
    Args:
        content: AI 응답 내용
    """
    st.session_state.messages.append({"role": "assistant", "content": content})


def get_conversation_history(exclude_last=False):
    """
    대화 히스토리 가져오기
    
    Args:
        exclude_last: 마지막 메시지를 제외할지 여부
    
    Returns:
        list: 대화 히스토리 리스트
    """
    if exclude_last and len(st.session_state.messages) > 1:
        return st.session_state.messages[:-1]
    return st.session_state.messages.copy()


def process_user_input(user_input):
    """
    사용자 입력을 처리하고 AI 응답 생성
    
    Args:
        user_input: 사용자 입력 텍스트
    
    Returns:
        str: AI 응답 텍스트
    """
    # 사용자 메시지 추가
    add_user_message(user_input)
    
    # 대화 히스토리 가져오기 (현재 메시지 제외)
    history = get_conversation_history(exclude_last=True)
    
    # Gemini API 호출
    response = ask_gemini(user_input, conversation_history=history)
    
    # AI 응답 추가
    add_assistant_message(response)
    
    return response

