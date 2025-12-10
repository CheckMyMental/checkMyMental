import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import traceback

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
        st.session_state.messages.append({
            "role": "assistant",
            "content": last_message.content
        })
    
    # 2. 단계별 산출물 디버깅용 저장 (선택 사항)
    # 필요 시 st.session_state에 저장하여 사이드바 등에서 확인 가능
    if "intake_summary_report" in state:
        st.session_state.debug_intake_summary = state["intake_summary_report"]
    if "diagnosis_result" in state: # state.py 필드명 확인 필요 (Validation 결과 등)
        st.session_state.debug_diagnosis = state.get("diagnosis_result")

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
    
    stage_num = stage_map.get(current_node, 0)
    
    return {
        "stage": stage_num,
        "name": current_node,
        "total_stages": 5
    }
