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
            st.rerun()


def render_main_header():
    # 메인 헤더 표시
    st.title("💬 AI 정신건강 상담 도우미")
    st.markdown("---")


def render_chat_messages(messages):
    # 채팅 메시지들을 화면에 표시
    for message in messages:
        # 가이드라인 메시지인지 확인
        is_guideline = message.get("is_guideline", False)

        if is_guideline:
            # 가이드라인 메시지는 다른 배경색으로 표시
            # 배경색 설정 (원하는 색상으로 변경 가능)
            bg_color_hex = "#FFDA9A"  # 배경색 (연한 파란색, 원하는 색으로 변경)
            border_color_hex = "#FFCC00"  # 테두리 색상 (진한 파란색, 원하는 색으로 변경)
            
            # hex 색상을 rgb로 변환 (배경색)
            bg_hex = bg_color_hex.lstrip("#")
            bg_rgb = tuple(int(bg_hex[i : i + 2], 16) for i in (0, 2, 4))
            bg_color_rgba = f"rgba({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]}, 0.8)"

            # 메시지 내용을 HTML로 감싸서 배경색 적용
            # HTML이 포함된 메시지이므로 unsafe_allow_html=True 필요
            styled_content = f"""
<div style="
    background: {bg_color_rgba};
    border-left: 4px solid {border_color_hex};
    padding: 1rem;
    border-radius: 8px;
    margin: 0;
    width: 100%;
    box-sizing: border-box;
">
{message["content"]}
</div>
"""
            with st.chat_message(message["role"]):
                st.markdown(styled_content, unsafe_allow_html=True)
        else:
            # 일반 메시지는 기본 스타일로 표시
            with st.chat_message(message["role"]):
                st.markdown(message["content"])


def render_user_input():
    # 사용자 입력창 표시
    return st.chat_input("지금 어떤 기분이신가요?")


def render_assistant_response(response):
    # AI 응답을 화면에 표시
    with st.chat_message("assistant"):
        st.markdown(response)


def render_stage_guideline():
    """현재 단계의 가이드라인을 채팅창 위에 표시"""
    from .chat_handler import get_current_stage_info
    from .stage_guidelines import STAGE_GUIDELINES

    stage_info = get_current_stage_info()
    if not stage_info:
        return

    current_stage = stage_info["stage"]
    guideline = STAGE_GUIDELINES.get(current_stage)

    if not guideline:
        return

    # 할 일 목록 생성
    what_to_do_items = "".join([f"<li>{item}</li>" for item in guideline["what_to_do"]])
    tips_items = "".join([f"<li>{item}</li>" for item in guideline["tips"]])

    # HTML 문자열 생성 (따옴표 이스케이프 처리)
    html_content = f"""<div style="background: linear-gradient(135deg, {guideline["color"]}15 0%, {guideline["color"]}05 100%); border-left: 4px solid {guideline["color"]}; padding: 1rem; margin: 1rem 0; border-radius: 8px;">
    <h4 style="color: {guideline["color"]}; margin-top: 0;">{guideline["title"]}</h4>
    <p style="color: #666; margin-bottom: 1rem;">{guideline["description"]}</p>
    <div style="margin-bottom: 0.5rem;">
        <strong style="color: {guideline["color"]};">이 단계에서 할 일:</strong>
        <ul style="margin-top: 0.5rem;">{what_to_do_items}</ul>
    </div>
    <div>
        <strong style="color: {guideline["color"]};">💡 유의사항:</strong>
        <ul style="margin-top: 0.5rem;">{tips_items}</ul>
    </div>
</div>"""

    # Streamlit info 박스 스타일로 표시
    st.markdown(html_content, unsafe_allow_html=True)


def render_stage_guideline_by_stage(stage: int):
    """입력된 단계 번호에 맞는 가이드라인을 표시"""
    from .stage_guidelines import STAGE_GUIDELINES
    
    guideline = STAGE_GUIDELINES.get(stage)
    if not guideline:
        return
    
    what_to_do_items = "".join([f"<li>{item}</li>" for item in guideline["what_to_do"]])
    tips_items = "".join([f"<li>{item}</li>" for item in guideline["tips"]])
    
    html_content = f"""<div style="background: linear-gradient(135deg, {guideline["color"]}15 0%, {guideline["color"]}05 100%); border-left: 4px solid {guideline["color"]}; padding: 1rem; margin: 1rem 0; border-radius: 8px;">
    <h4 style="color: {guideline["color"]}; margin-top: 0;">{guideline["title"]}</h4>
    <p style="color: #666; margin-bottom: 1rem;">{guideline["description"]}</p>
    <div style="margin-bottom: 0.5rem;">
        <strong style="color: {guideline["color"]};">이 단계에서 할 일:</strong>
        <ul style="margin-top: 0.5rem;">{what_to_do_items}</ul>
    </div>
    <div>
        <strong style="color: {guideline["color"]};">💡 유의사항:</strong>
        <ul style="margin-top: 0.5rem;">{tips_items}</ul>
    </div>
</div>"""
    st.markdown(html_content, unsafe_allow_html=True)
