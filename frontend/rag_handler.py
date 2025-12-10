# RAG 핸들러 모듈
import json
import re
import httpx
from typing import Dict, Optional


def parse_summary_string(internal_data: str) -> str:
    """
    ---INTERNAL_DATA---에서 Summary String 내용 추출
    
    Args:
        internal_data: ---INTERNAL_DATA--- 이후의 전체 텍스트
    
    Returns:
        Summary String의 실제 내용 (Summary String: 제외)
    """
    # "Summary String:" 이후의 내용 추출
    if "Summary String:" in internal_data:
        # "Summary String:" 이후의 모든 내용 가져오기
        parts = internal_data.split("Summary String:", 1)
        if len(parts) > 1:
            summary_content = parts[1].strip()
            return summary_content
    
    # Summary String:이 없으면 전체를 반환
    return internal_data.strip()


def create_rag_hypothesis_request(summary_string: str, top_k: int = 12, diag_top_n: int = 3) -> Dict:
    """
    Summary String을 RAG Hypothesis API 요청 형식으로 변환
    
    Args:
        summary_string: Summary String의 실제 내용
        top_k: 검색할 문단 수 (기본값: 12)
        diag_top_n: 상위 질환 수 (기본값: 3)
    
    Returns:
        RAG Hypothesis API 요청용 JSON 딕셔너리
    """
    return {
        "intake_report": summary_string,
        "top_k": top_k,
        "diag_top_n": diag_top_n
    }


def call_rag_hypothesis_api(request_data: Dict, api_url: str = "http://localhost:8000/rag/hypothesis") -> Optional[Dict]:
    """
    RAG Hypothesis API를 호출하여 질환 후보 검색
    
    Args:
        request_data: RAG API 요청 데이터
        api_url: RAG API 엔드포인트 URL
    
    Returns:
        RAG API 응답 데이터 (실패 시 None)
    """
    try:
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=request_data)
            response.raise_for_status()
            result = response.json()
            
            
            return result
            
    except httpx.RequestError as e:
        return None
    except httpx.HTTPStatusError as e:
        return None
    except Exception as e:
        return None


def process_stage2_rag_hypothesis(internal_data: str, top_k: int = 12, diag_top_n: int = 3) -> Optional[Dict]:
    """
    Stage 2에서 Summary String을 파싱하고 RAG Hypothesis API를 호출하는 전체 프로세스
    
    Args:
        internal_data: ---INTERNAL_DATA--- 이후의 전체 텍스트
        top_k: 검색할 문단 수 (기본값: 12)
        diag_top_n: 상위 질환 수 (기본값: 3)
    
    Returns:
        RAG API 응답 데이터 (실패 시 None)
    """
    # 1. Summary String 추출
    summary_string = parse_summary_string(internal_data)
    
    if not summary_string:
        return None
    
    # 2. RAG Hypothesis API 요청 데이터 생성
    request_data = create_rag_hypothesis_request(summary_string, top_k=top_k, diag_top_n=diag_top_n)
    
    # 3. RAG Hypothesis API 호출
    rag_result = call_rag_hypothesis_api(request_data)
    
    return rag_result


def call_rag_solution_api(diagnosis: str, api_url: str = "http://localhost:8000/rag/solution") -> Optional[Dict]:
    """
    RAG API를 호출하여 확정 질환명의 솔루션 검색
    
    Args:
        diagnosis: 확정된 질환명
        api_url: RAG API 엔드포인트 URL
    
    Returns:
        RAG API 응답 데이터 (실패 시 None)
        {
            "diagnosis": "string",
            "evidence": []
        }
    """
    try:
        request_data = {
            "diagnosis": diagnosis
        }
        
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, json=request_data)
            response.raise_for_status()
            result = response.json()
            


            return result
            
    except httpx.RequestError as e:
        return None
    except httpx.HTTPStatusError as e:
        return None
    except Exception as e:
        return None


def process_stage4_rag_solution(diagnosis: str) -> Optional[Dict]:
    """
    Stage 4에서 확정 질환명으로 솔루션을 검색하는 프로세스
    
    Args:
        diagnosis: 확정된 질환명
    
    Returns:
        RAG API 응답 데이터 (실패 시 None)
    """
    if not diagnosis or not diagnosis.strip():
        return None
    
    # RAG API 호출
    rag_result = call_rag_solution_api(diagnosis.strip())
    
    return rag_result

