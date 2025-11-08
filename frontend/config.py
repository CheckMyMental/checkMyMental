
import os
from dotenv import load_dotenv
import streamlit as st

# 환경 변수 설정 및 검증 모듈

# 환경 변수 로드
load_dotenv()

# Gemini API 키가 설정되어 있는지 확인하고, 없으면 에러 메시지 표시
def check_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        st.stop()
        return False
    return True

# 환경 변수에서 API 키 가져오기
def get_api_key():
    return os.getenv("GEMINI_API_KEY")

