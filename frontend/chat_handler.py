import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import traceback
from typing import Optional, Dict, Any

from .graph_client import get_graph_client

def init_chat_history():
    """
    채팅 히스토리 및 관련 상태 초기화
    """
    # 1. 메시지 히스토리 초기화 (Streamlit UI용)
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
        # 초기 인사 메시지 추가
        greeting_message = "안녕하세요! 저는 AI 정신건강 상담 도우미입니다. 오늘 어떤 도움이 필요하신가요? 편하게 말씀해주세요."
        st.session_state.messages.append({
            "role": "assistant",
            "content": greeting_message
        })
    
    # 2. Graph Client 초기화 및 세션 ID 설정
    if "graph_client" not in st.session_state:
        st.session_state.graph_client = get_graph_client()
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = st.session_state.graph_client.create_thread_id()
        print(f"[ChatHandler] New session initialized with thread_id: {st.session_state.thread_id}")

def process_user_input(user_input: str):
    """
    사용자 입력을 처리하고 Graph를 실행하여 응답을 생성
    
    Args:
        user_input: 사용자 입력 텍스트
    """
    if not user_input:
        return

    # 1. 사용자 메시지 UI 추가
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Graph 실행
    graph_client = st.session_state.graph_client
    thread_id = st.session_state.thread_id
    
    try:
        # Graph Invoke (Blocking)
        # 실제 구현에서는 stream_graph를 사용하여 토큰 스트리밍을 구현할 수 있음
        final_state = graph_client.invoke_graph(user_input, thread_id)
        
        # 3. 결과 동기화 (State -> UI)
        _sync_state_to_ui(final_state)
        
    except Exception as e:
        # 전체 스택트레이스를 함께 출력하여 정확한 예외 발생 위치를 확인
        print("[ChatHandler] Error executing graph:")
        print(traceback.format_exc())
        print(f"[ChatHandler] Error message: {e}")
        st.error("상담 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

def _sync_state_to_ui(state: dict):
    """
    Graph 실행 결과(State)를 Streamlit UI 세션 상태와 동기화
    
    Args:
        state: 실행 완료된 CounselingState 딕셔너리
    """
    # 1. 메시지 동기화
    # LangGraph의 messages는 전체 히스토리이므로, 
    # Streamlit messages보다 최신인(마지막) 메시지만 추가하거나,
    # 전체를 다시 매핑하는 방식을 선택할 수 있음.
    # 여기서는 마지막 AI 메시지를 가져와 추가하는 방식 사용
    
    graph_messages = state.get("messages", [])
    if not graph_messages:
        return
        
    last_message = graph_messages[-1]

    # 마지막 메시지가 AI 메시지인 경우에만 UI에 추가
    # (사용자 메시지는 이미 process_user_input 초반에 추가됨)
    if isinstance(last_message, AIMessage):
        # Solution 단계의 최종 요약 메시지는 줄바꿈이 유지되도록 HTML로 감싸서 렌더링
        is_solution_final = "final_summary_string" in state or "solution_content" in state
        if is_solution_final:
            content_html = (
                "<div style='white-space: pre-line; line-height: 1.6; font-size: 0.95rem;'>"
                f"{last_message.content}"
                "</div>"
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": content_html,
                    "is_html": True,
                }
            )
        else:
            st.session_state.messages.append(
                {"role": "assistant", "content": last_message.content}
            )
    
    # 2. 단계별 산출물 디버깅용 저장 (선택 사항)
    # 필요 시 st.session_state에 저장하여 사이드바 등에서 확인 가능
    if "intake_summary_report" in state:
        st.session_state.debug_intake_summary = state["intake_summary_report"]
    if "diagnosis_result" in state:  # state.py 필드명 확인 필요 (Validation 결과 등)
        st.session_state.debug_diagnosis = state.get("diagnosis_result")

    # 3. 최종 요약 카드 (Solution 단계용)
    # Solution 단계가 완료되면 final_summary_string/solution_content가 함께 존재하므로,
    # 이 시점에 Validation/Severity 결과를 시각적으로 정리한 카드 UI를 추가로 렌더링한다.
    if "final_summary_string" in state or "solution_content" in state:
        html_card = _build_final_result_card(state)
        if html_card:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": html_card,
                    "is_html": True,
                }
            )

def get_current_stage_info():
    """
    현재 진행 중인 상담 단계 정보를 반환
    (Graph의 현재 노드 정보를 기반으로 추론)
    """
    if "graph_client" not in st.session_state or "thread_id" not in st.session_state:
        return None
        
    client = st.session_state.graph_client
    snapshot = client.get_state_snapshot(st.session_state.thread_id)
    
    # 현재 대기 중인 다음 노드 확인 (next는 튜플)
    next_nodes = snapshot.get("next", [])
    current_node = next_nodes[0] if next_nodes else "unknown"
    
    # 노드 이름 매핑
    stage_map = {
        "intake": 1,
        "hypothesis": 2,
        "validation": 3,
        "severity": 4,
        "solution": 5,
        "__end__": 6
    }


def _build_final_result_card(state: Dict[str, Any]) -> Optional[str]:
    """
    최종 단계에서 최종 평가 질환과 해당 확률(가능한 경우)을
    시각적으로 보기 좋게 정리한 HTML 카드 생성.
    """
    validation_probs = state.get("validation_probabilities") or {}
    severity_dx = state.get("severity_diagnosis")
    severity_text = state.get("severity_result_string") or ""

    if not validation_probs and not severity_dx:
        return None

    # 최종 질환에 대한 확률만 추출 (있을 때만)
    final_prob = None
    if severity_dx and validation_probs:
        try:
            if severity_dx in validation_probs:
                final_prob = float(validation_probs[severity_dx])
        except Exception:
            final_prob = None

    lines = []
    lines.append(
        """
<div style="
    border-radius: 12px;
    border: 1px solid #e0e0e0;
    padding: 16px 18px;
    margin-top: 12px;
    background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
">
"""
    )
    lines.append(
        '<div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 4px;">최종 진단 요약</div>'
    )
    lines.append(
        '<div style="font-size: 0.85rem; color: #666; margin-bottom: 10px;">'
        "이번 상담을 바탕으로 계산된 최종 평가 질환과 그 의미를 정리한 내용입니다."
        "</div>"
    )

    # 최종 평가 질환 영역 (+ 가능하면 해당 확률 퍼센트)
    if severity_dx:
        lines.append(
            '<div style="margin-top: 12px; font-weight: 600; font-size: 0.9rem;">최종 평가 질환</div>'
        )
        subtitle = ""
        if final_prob is not None:
            pct = final_prob * 100 if final_prob <= 1.0 else final_prob
            pct = max(0.0, min(pct, 100.0))
            subtitle = f" (추정 확률 약 {pct:.0f}%)"
            # 퍼센트 바 (최종 질환만)
            bar_value = final_prob if final_prob <= 1.0 else final_prob / 100.0
            bar_value = max(0.0, min(bar_value, 1.0))
        lines.append(
            f'<div style="font-size: 0.9rem; margin-top: 2px;"><span style="font-weight:700; color:#2c3e50;">{severity_dx}</span>{subtitle}</div>'
        )
        if final_prob is not None:
            bar_width = int(bar_value * 100)
            lines.append(
                f"""
<div style="width: 100%; height: 7px; background: #f1f1f1; border-radius: 999px; overflow: hidden; margin-top: 4px; margin-bottom: 4px;">
  <div style="width: {bar_width}%; height: 100%; background: linear-gradient(90deg, #16a34a, #22c55e);"></div>
</div>
"""
            )
        if severity_text:
            preview = (
                severity_text[:180] + "..."
                if len(severity_text) > 180
                else severity_text
            )
            lines.append(
                f'<div style="font-size: 0.8rem; color:#555; margin-top: 4px;">{preview}</div>'
            )

    lines.append("</div>")
    return "\n".join(lines)
