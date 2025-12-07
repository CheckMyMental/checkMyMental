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
    
    # --- 디버그/상태 패널 (개발자용) ---
    with st.sidebar.expander("🛠️ 디버그 패널 (상태 정보)", expanded=True):
        if "thread_id" in st.session_state:
            st.markdown(f"**Session ID:** `{st.session_state.thread_id[:8]}...`")

            client = get_graph_client()
            try:
                snapshot = client.get_state_snapshot(st.session_state.thread_id)
                state_values = snapshot.get("values", {})
                next_nodes = snapshot.get("next", [])

                # 현재 노드 표시
                current_node = next_nodes[0] if next_nodes else "unknown"
                st.markdown(f"**다음 실행 노드:** `{current_node}`")
                st.markdown("---")

                # ========== Stage 1: Intake ==========
                st.markdown("### 📝 Stage 1: Intake")
                intake_summary = state_values.get("intake_summary_report")
                domain_active = state_values.get("domain_questions_active", False)
                current_domain = state_values.get("current_domain")

                if intake_summary:
                    st.success("✅ **intake_summary_report** 생성됨")
                    st.caption(f"길이: {len(intake_summary)} 문자")
                    with st.expander("요약 내용 보기"):
                        st.text(intake_summary[:300] + "...")
                    st.info("→ **다음 단계**: Hypothesis로 자동 이동")
                else:
                    st.warning("⏳ **intake_summary_report** 대기 중")
                    st.caption("5가지 필수 정보 수집 필요:")
                    st.caption("• Chief Complaint (주 호소)")
                    st.caption("• Onset (시작 시기)")
                    st.caption("• Frequency & Duration (빈도/지속)")
                    st.caption("• Impairment (일상생활 지장)")
                    st.caption("• History (과거력)")

                if domain_active:
                    st.info(f"🔍 도메인 심화 질문 진행 중: **{current_domain}**")

                st.markdown("---")

                # ========== Stage 2: Hypothesis ==========
                st.markdown("### 🔬 Stage 2: Hypothesis")
                hypothesis_criteria = state_values.get("hypothesis_criteria")

                if hypothesis_criteria:
                    st.success(f"✅ **hypothesis_criteria** 생성됨 ({len(hypothesis_criteria)}개)")
                    with st.expander("진단 기준 보기"):
                        for i, criteria in enumerate(hypothesis_criteria[:3], 1):
                            st.caption(f"{i}. {criteria[:100]}...")
                    st.info("→ **다음 단계**: Validation으로 무조건 이동")
                else:
                    st.warning("⏳ **hypothesis_criteria** 대기 중")
                    st.caption("RAG 검색으로 의심 질환 후보 도출")

                st.markdown("---")

                # ========== Stage 3: Validation ==========
                st.markdown("### ✅ Stage 3: Validation")
                validation_probs = state_values.get("validation_probabilities")
                is_re_intake = state_values.get("is_re_intake", False)
                severity_diagnosis = state_values.get("severity_diagnosis")

                if validation_probs:
                    st.success("✅ **validation_probabilities** 계산됨")

                    # 확률 표시
                    max_prob = max(validation_probs.values()) if validation_probs else 0
                    max_disease = max(validation_probs.items(), key=lambda x: x[1])[0] if validation_probs else "None"

                    st.metric("최대 확률", f"{max_prob:.1%}", delta=f"{max_disease}")

                    with st.expander("전체 확률 보기"):
                        for disease, prob in validation_probs.items():
                            st.caption(f"• {disease}: {prob:.1%}")

                    # 다음 단계 결정
                    if is_re_intake:
                        st.error("→ **Re-Intake**: 확률 ≤ 0.5 → Stage 1로 복귀")
                    elif severity_diagnosis:
                        st.info(f"→ **Severity 진행**: 확정 진단 `{severity_diagnosis}`")
                    else:
                        st.warning("⚠️ 상태 불일치 (확률은 있지만 진단명 없음)")
                else:
                    st.warning("⏳ **validation_probabilities** 대기 중")
                    st.caption("5지선다 질문으로 확률 계산 필요")

                if severity_diagnosis and not is_re_intake:
                    st.success(f"✅ **severity_diagnosis** 설정: `{severity_diagnosis}`")

                st.markdown("---")

                # ========== Stage 4: Severity ==========
                st.markdown("### 📊 Stage 4: Severity")
                severity_result = state_values.get("severity_result_string")

                if severity_result:
                    st.success("✅ **severity_result_string** 생성됨")
                    st.caption(f"길이: {len(severity_result)} 문자")
                    with st.expander("심각도 평가 결과 보기"):
                        st.text(severity_result[:200] + "...")
                    st.info("→ **다음 단계**: Solution으로 자동 이동")
                else:
                    if severity_diagnosis:
                        st.warning("⏳ **severity_result_string** 대기 중")
                        st.caption(f"대상 질환: {severity_diagnosis}")
                    else:
                        st.caption("아직 Stage 3 미완료")

                st.markdown("---")

                # ========== Stage 5: Solution ==========
                st.markdown("### 💡 Stage 5: Solution")
                final_summary = state_values.get("final_summary_string")
                solution_content = state_values.get("solution_content")

                if solution_content:
                    st.success("✅ **solution_content** 생성됨")
                    st.caption("상담 완료!")
                elif final_summary:
                    st.info("🔄 최종 요약 생성 중...")
                else:
                    st.caption("아직 Stage 4 미완료")

                st.markdown("---")

                # ========== 전환 조건 요약 ==========
                with st.expander("📋 전환 조건 요약표"):
                    st.markdown("""
**Intake → Hypothesis**
- 조건: `intake_summary_report` 존재
- 현재: """ + ("✅ 충족" if intake_summary else "❌ 미충족") + """

**Hypothesis → Validation**
- 조건: 무조건 이동
- 현재: """ + ("✅" if hypothesis_criteria else "⏳") + """

**Validation → Severity or Intake**
- Severity 조건: `severity_diagnosis` 존재 & `is_re_intake=False`
- Re-Intake 조건: `is_re_intake=True`
- 현재: """ + (
    "✅ Severity 진행" if (severity_diagnosis and not is_re_intake) else
    "🔄 Re-Intake" if is_re_intake else
    "❌ 미충족"
) + """

**Severity → Solution**
- 조건: `severity_result_string` 존재
- 현재: """ + ("✅ 충족" if severity_result else "❌ 미충족") + """

**Solution → END**
- 조건: 무조건 종료
                    """)

                # 전체 State Raw View
                if st.checkbox("🔧 Show Raw State (전체)"):
                    st.json({k: str(v)[:100] + "..." if isinstance(v, str) and len(v) > 100 else v
                             for k, v in state_values.items() if k != "messages"})

            except Exception as e:
                st.error(f"❌ State 로드 오류: {e}")
        else:
            st.warning("⚠️ Session not initialized")

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
        is_html = message.get("is_html", False) # TODO: Graph 전환 시 필드 확인 필요

        with st.chat_message(message["role"]):
             # 새로 추가된 Assistant 메시지만 타이핑 효과 적용
             # 이미 표시된 메시지는 바로 표시
            if message["role"] == "assistant" and idx >= st.session_state.rendered_message_count:
                _render_typing_effect(message["content"])
            else:
                if is_html:
                    st.markdown(message["content"], unsafe_allow_html=True)
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
