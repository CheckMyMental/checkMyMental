import uuid
from typing import Optional, Any, Dict, Generator
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage

from graph.graph_builder import build_graph
from graph.state import CounselingState

class GraphClient:
    """
    LangGraph 클라이언트 래퍼 클래스
    - 그래프 초기화 및 로드
    - 체크포인터(Memory) 관리
    - 실행 설정(Config) 관리
    
    Singleton 패턴을 사용하여 애플리케이션 전역에서 하나의 그래프 인스턴스와
    메모리 저장소를 공유합니다. (Streamlit은 멀티스레드 환경이므로 주의 필요)
    """
    _instance = None
    _graph: Optional[CompiledStateGraph] = None
    _checkpointer: Optional[MemorySaver] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GraphClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """그래프 및 체크포인터 초기화"""
        # In-memory checkpointer (세션 간 상태 저장)
        # 실제 프로덕션에서는 Redis, Postgres 등을 사용할 수 있음
        self._checkpointer = MemorySaver()
        
        # 체크포인터를 주입하여 그래프 빌드 (컴파일)
        self._graph = build_graph(checkpointer=self._checkpointer)
        
        print("[GraphClient] Graph initialized with MemorySaver")

    @property
    def graph(self) -> CompiledStateGraph:
        """컴파일된 그래프 인스턴스 반환"""
        if self._graph is None:
            self._initialize()
        return self._graph

    def get_config(self, thread_id: str) -> RunnableConfig:
        """
        특정 세션(thread_id)에 대한 실행 설정(RunnableConfig) 생성
        
        Args:
            thread_id: 사용자 세션 고유 ID
            
        Returns:
            RunnableConfig: thread_id가 포함된 설정 객체
        """
        return {"configurable": {"thread_id": thread_id}}

    def create_thread_id(self) -> str:
        """새로운 thread_id(UUID) 생성"""
        return str(uuid.uuid4())

    def invoke_graph(self, user_input: str, thread_id: str) -> CounselingState:
        """
        사용자 입력을 그래프에 전달하고 실행 (Blocking)
        
        Args:
            user_input: 사용자 입력 메시지
            thread_id: 세션 ID
            
        Returns:
            CounselingState: 실행 완료 후의 최종 상태
        """
        config = self.get_config(thread_id)
        
        # 입력 상태 생성 (HumanMessage 추가)
        initial_state = {
            "messages": [HumanMessage(content=user_input)]
        }
        
        # 그래프 실행
        result = self.graph.invoke(initial_state, config=config)
        return result

    def stream_graph(self, user_input: str, thread_id: str) -> Generator[Dict[str, Any], None, None]:
        """
        사용자 입력을 그래프에 전달하고 스트리밍 실행
        
        Args:
            user_input: 사용자 입력 메시지
            thread_id: 세션 ID
            
        Yields:
            Dict: 그래프 실행 중 발생하는 이벤트/청크 (노드 업데이트 등)
        """
        config = self.get_config(thread_id)
        
        # 입력 상태 생성
        initial_state = {
            "messages": [HumanMessage(content=user_input)]
        }
        
        # 그래프 스트리밍 실행 (모든 업데이트 수신)
        return self.graph.stream(initial_state, config=config, stream_mode="updates")

    def get_state_snapshot(self, thread_id: str) -> Dict[str, Any]:
        """
        현재 그래프의 상태 스냅샷(StateSnapshot) 조회
        
        Args:
            thread_id: 세션 ID
            
        Returns:
            Dict: {
                "values": CounselingState 값,
                "next": 다음 실행될 노드 목록,
                "config": 현재 설정
            }
        """
        config = self.get_config(thread_id)
        snapshot = self.graph.get_state(config)
        
        return {
            "values": snapshot.values,
            "next": snapshot.next,
            "config": snapshot.config,
            "metadata": snapshot.metadata,
            "created_at": snapshot.created_at
        }

# 전역 인스턴스 접근용 헬퍼 함수
def get_graph_client() -> GraphClient:
    return GraphClient()
