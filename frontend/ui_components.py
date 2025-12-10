# UI 컴포넌트 모듈
import streamlit as st
import time
import json

from .chat_handler import get_current_stage_info
from .graph_client import get_graph_client

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
    stage_info = get_current_stage_info()

    stages = [
        ("1.초기 접수 (Intake)", "증상과 감정을 수집합니다", "#2E5C8A"),
        ("2.가설 생성 (Hypothesis Generation)", "관련 질환을 검색 중입니다", "#2D8659"),
        ("3.진단 검증 (Validation)", "질환을 감별하고 확정합니다", "#CC6F35"),
        (
            "4.심각도 평가 (Severity)", 
            "증상의 심각도를 평가합니다", 
            "#D35400"
        ),
        (
            "5.솔루션 및 요약 (Solution & Summary)",
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

    # --- 사용자용 진단 요약 카드 ---
    if "thread_id" in st.session_state:
        client = get_graph_client()
        try:
            snapshot = client.get_state_snapshot(st.session_state.thread_id)
            state_values = snapshot.get("values", {})

            validation_probs = state_values.get("validation_probabilities") or {}
            severity_dx = state_values.get("severity_diagnosis")
            severity_text = state_values.get("severity_result_string") or ""

            if validation_probs or severity_dx:
                st.sidebar.markdown(
                    "<p style='font-weight: bold; font-size: 1.1em; margin-bottom: 4px;'>🧠 진단 요약</p>",
                    unsafe_allow_html=True,
                )

                # 3단계: 질환별 확률 바
                if validation_probs:
                    st.sidebar.markdown(
                        "<span style='font-size: 0.85em; color: #666;'>검증 단계에서 계산된 질환별 확률입니다.</span>",
                        unsafe_allow_html=True,
                    )
                    try:
                        items = sorted(
                            validation_probs.items(),
                            key=lambda x: float(x[1]),
                            reverse=True,
                        )
                    except Exception:
                        items = list(validation_probs.items())

                    for diag_name, prob in items:
                        try:
                            p = float(prob)
                        except Exception:
                            continue

                        # 0~1 또는 0~100 둘 다 대응
                        bar_value = p if p <= 1.0 else p / 100.0
                        pct = p * 100 if p <= 1.0 else p
                        bar_value = max(0.0, min(bar_value, 1.0))

                        st.sidebar.markdown(
                            f"<span style='font-size: 0.9em;'><b>{diag_name}</b>: {pct:.0f}%</span>",
                            unsafe_allow_html=True,
                        )
                        st.sidebar.progress(bar_value)

                # 4단계: 최종 평가 질환 및 한 줄 요약
                if severity_dx:
                    st.sidebar.markdown(
                        "<hr style='margin: 8px 0 4px 0; border: none; border-top: 1px solid #eee;' />",
                        unsafe_allow_html=True,
                    )
                    st.sidebar.markdown(
                        f"<span style='font-size: 0.9em;'><b>최종 평가 질환</b>: {severity_dx}</span>",
                        unsafe_allow_html=True,
                    )
                    if severity_text:
                        preview = (
                            severity_text[:120] + "..."
                            if len(severity_text) > 120
                            else severity_text
                        )
                        st.sidebar.markdown(
                            f"<span style='font-size: 0.8em; color: #666;'>{preview}</span>",
                            unsafe_allow_html=True,
                        )

                st.sidebar.markdown("---")

        except Exception as e:
            # 사용자용 요약은 실패해도 조용히 무시 (디버그 패널에서 상태 확인 가능)
            print(f"[Sidebar Debug] 진단 요약 렌더링 오류: {e}")

    # --- 디버그/상태 패널 (개발자용) ---
    with st.sidebar.expander("🛠️ 디버그 패널 (상태 정보)", expanded=False):
        if "thread_id" in st.session_state:
            st.markdown(f"**Session ID:** `{st.session_state.thread_id}`")
            
            client = get_graph_client()
            try:
                snapshot = client.get_state_snapshot(st.session_state.thread_id)
                state_values = snapshot.get("values", {})
                
                st.markdown("### Current State Data")
                
                # 1단계: 요약 리포트
                if state_values.get("intake_summary_report"):
                    st.info("✅ Intake Summary Available")
                    with st.popover("Show Summary"):
                        st.code(state_values["intake_summary_report"])
                
                # 2단계: 가설
                if state_values.get("hypothesis_criteria"):
                    st.success("✅ Hypothesis Criteria")
                    with st.popover("Show Criteria"):
                        st.json(state_values["hypothesis_criteria"])
                
                # 3단계: 검증 결과
                if state_values.get("validation_probabilities"):
                     st.warning("✅ Validation Probs")
                     st.write(state_values["validation_probabilities"])
                
                # 전체 State Raw View
                if st.checkbox("Show Raw State"):
                    st.json({k: v for k, v in state_values.items() if k != "messages"})
                    
            except Exception as e:
                st.error(f"Error fetching state: {e}")
        else:
            st.text("Session not initialized")

    st.sidebar.markdown("---")

    # 초기화 버튼
    if st.sidebar.button("새 상담 시작"):
        # 세션 상태 초기화
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def render_main_header():
    # 메인 헤더 표시
    st.title("💬 AI 정신건강 상담 도우미")
    st.markdown("---")


def render_chat_messages(messages):
    # 이미 렌더링된 메시지 수 추적
    if "rendered_message_count" not in st.session_state:
        st.session_state.rendered_message_count = 0
    
    # 채팅 메시지들을 화면에 표시
    for idx, message in enumerate(messages):
        # 가이드라인 메시지 (HTML 포함) 등 특수 메시지 처리
        is_html = message.get("is_html", False)  # TODO: Graph 전환 시 필드 확인 필요

        with st.chat_message(message["role"]):
            # HTML 컨텐츠는 항상 그대로 렌더링 (타이핑 효과 적용 X)
            if is_html:
                st.markdown(message["content"], unsafe_allow_html=True)
            # 새로 추가된 Assistant 메시지만 타이핑 효과 적용
            # 이미 표시된 메시지는 바로 표시
            elif (
                message["role"] == "assistant"
                and idx >= st.session_state.rendered_message_count
            ):
                _render_typing_effect(message["content"])
            else:
                st.markdown(message["content"])
    
    # 렌더링된 메시지 수 업데이트
    st.session_state.rendered_message_count = len(messages)


def render_user_input():
    # 사용자 입력 제어
    # Graph가 실행 중이거나 특정 종료 상태인 경우 입력 비활성화 가능
    # 현재는 단순 구현
    
    # 단계 정보 확인 (종료 단계 등)
    stage_info = get_current_stage_info()
    disabled = False
    placeholder = "지금 어떤 기분이신가요?"
    
    if stage_info and stage_info.get("stage") == 6: # End
        disabled = True
        placeholder = "상담이 종료되었습니다. '새 상담 시작'을 눌러주세요."
        
    return st.chat_input(placeholder, disabled=disabled)


def _render_typing_effect(text, speed=0.02):
    """
    타이핑 효과로 텍스트를 표시
    
    Args:
        text: 표시할 텍스트
        speed: 각 문자 사이의 딜레이 (초)
    """
    # Streamlit의 write_stream을 사용 (1.28.0+)
    # 버전이 낮으면 fallback으로 일반 표시
    try:
        # 텍스트를 문자 단위로 나눠서 스트림으로 전달
        def text_generator():
            for char in text:
                yield char
                time.sleep(speed)
        
        st.write_stream(text_generator())
    except AttributeError:
        # write_stream이 없는 경우 일반 표시
        st.markdown(text)
