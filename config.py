"""
환경 변수 설정 및 검증 모듈
"""
import os
from dotenv import load_dotenv
import streamlit as st

# 환경 변수 로드
load_dotenv()


def check_api_key():
    """
    Gemini API 키가 설정되어 있는지 확인하고, 없으면 에러 메시지 표시
    
    Returns:
        bool: API 키가 설정되어 있으면 True, 없으면 False
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        st.stop()
        return False
    return True


def get_api_key():
    """
    환경 변수에서 API 키 가져오기
    
    Returns:
        str: API 키
    """
    return os.getenv("GEMINI_API_KEY")

