import os  # 운영체제 다루는 기본 모듈 , .env파일 불러올때 사용함
import google.generativeai as genai  # 제미나이 모델을 python에서 쓸 수 있게 해주는 공식 SDK
from dotenv import (
    load_dotenv,
)  # 파일 안에 적힌 환경 변수들을 프로그램 실행 시 자동으로 불러오는 역할

# 환경 변수 로드
load_dotenv()
# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# GEMINI_API_KEY가 환경 변수에 설정되어 있는지 확인
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    raise ValueError(
        "GEMINI_API_KEY가 환경 변수에 설정되지 않았습니다. .env 파일을 확인해주세요."
    )

#========================================================================================================
# ask_gemnini()함수 정의 / 사용자 질문 -> Gemini API 호출 -> 응답 반환
# Gemini API를 호출하여 응답을 생성합니다.

# Args:
#     user_input: 사용자 입력 메시지
#     context: 추가 컨텍스트 (RAG 검색 결과 등)
#     conversation_history: 대화 히스토리 리스트

# Returns:
#     Gemini의 응답 텍스트
#========================================================================================================

def ask_gemini(
    user_input: str, context: str = None, conversation_history: list = None
) -> str:
    try:
        # 모델 초기화
        model = genai.GenerativeModel("gemini-2.0-flash")

        # 프롬프트 구성
        prompt = user_input

        # 컨텍스트가 있으면 추가
        if context:
            prompt = f"""다음 정보를 참고하여 사용자의 질문에 답변해주세요.
참고 정보:
{context}

사용자 질문: {user_input}
"""

        # 대화 히스토리가 있으면 포함
        if conversation_history:
            # 히스토리를 프롬프트에 포함
            history_text = "\n".join(
                [
                    f"{'사용자' if msg['role'] == 'user' else '상담사'}: {msg['content']}"
                    for msg in conversation_history[-5:]  # 최근 5개만 포함
                ]
            )
            prompt = f"""이전 대화:      
{history_text}

현재 사용자 질문: {user_input}
"""

        # API 호출
        response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"






