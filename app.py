import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title="AI 상담 프로토타입",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바 - 상담 단계 표시
st.sidebar.title("📋 상담 단계")
st.sidebar.markdown("""
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
""")

# 메인 UI
st.title("💬 AI 정신건강 상담 도우미")
st.markdown("---")

# 채팅 히스토리 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
user_input = st.chat_input("지금 어떤 기분이신가요?")

if user_input:
    # 사용자 메시지 추가 및 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # TODO: Gemini API 호출 및 응답 처리
    # 현재는 임시 응답
    with st.chat_message("assistant"):
        response = "안녕하세요! 지금 기분이 어떠신지 말씀해 주세요. 제가 도와드리겠습니다."
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

