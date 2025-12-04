import uuid
from typing import Optional, Any
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig

from graph.graph_builder import build_graph

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

# 전역 인스턴스 접근용 헬퍼 함수
def get_graph_client() -> GraphClient:
    return GraphClient()

