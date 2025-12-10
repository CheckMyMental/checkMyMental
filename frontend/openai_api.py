import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from .context_handler import get_context

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY가 환경 변수에 설정되지 않았습니다. .env 파일을 확인해주세요."
    )

# OpenAI 클라이언트 초기화 (lazy initialization)
# 모듈 로드 시점에 초기화하지 않고, 함수 내에서 필요할 때 초기화
# 이렇게 하면 proxies 등 환경 변수 문제를 피할 수 있습니다
_client_instance = None

def get_openai_client():
    """OpenAI 클라이언트를 싱글톤으로 반환"""
    global _client_instance
    if _client_instance is None:
        # 환경 변수에서 proxies 관련 설정 임시 제거
        import os
        env_backup = {}
        problematic_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
        
        # 프록시 환경 변수 백업 및 제거
        for key in problematic_keys:
            if key in os.environ:
                env_backup[key] = os.environ.pop(key)
        
        try:
            # httpx 클라이언트를 명시적으로 생성 (proxies 파라미터 없이)
            import httpx
            http_client = httpx.Client(
                timeout=60.0
            )
            
            # OpenAI 클라이언트 초기화 (http_client 명시)
            _client_instance = OpenAI(
                api_key=OPENAI_API_KEY,
                http_client=http_client
            )
        except Exception as e:
            # 환경 변수 복원
            for key, value in env_backup.items():
                os.environ[key] = value
            
            # http_client 없이 재시도
            try:
                _client_instance = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as e2:
                import traceback
                raise e2
        finally:
            # 환경 변수 복원
            for key, value in env_backup.items():
                if key not in os.environ:  # 이미 복원되지 않은 경우만
                    os.environ[key] = value
                    
    return _client_instance

# 기본 모델 설정
DEFAULT_MODEL = "gpt-4o-mini"  # 또는 "gpt-4", "gpt-3.5-turbo" 등

#========================================================================================================
# ask_gemini()함수 정의 / 사용자 질문 -> OpenAI API 호출 -> 응답 반환
# 호환성을 위해 함수 이름은 ask_gemini로 유지하되, 내부는 OpenAI API를 사용합니다.
#
# Args:
#     user_input: 사용자 입력 메시지
#     context : 추가 컨텍스트 (시스템 프롬프트 등)
#     conversation_history: 대화 히스토리 리스트
#     context_file: 컨텍스트 파일 이름
#
# Returns:
#     OpenAI의 응답 텍스트
#========================================================================================================

def ask_openai(
    user_input: str, 
    context: str = None, 
    conversation_history: list = None, 
    context_file: str = None,
    model: str = None
) -> str:
    """
    OpenAI API를 사용하여 LLM 응답 생성
    """
    try:
        # 모델 선택
        model_name = model or DEFAULT_MODEL
        
        # 컨텍스트 처리: context 파라미터가 없으면 파일에서 로드
        if context is None and context_file is not None:
            context = get_context(context_file)
        elif context is None:
            context = None

        # OpenAI 메시지 형식으로 변환
        messages = []
        
        # 1. 시스템 메시지 (컨텍스트가 있으면 시스템 메시지로 추가)
        if context:
            messages.append({
                "role": "system",
                "content": context
            })
        
        # 2. 대화 히스토리 추가 (최대 10개 메시지 = 5쌍)
        if conversation_history:
            limited_history = conversation_history[-10:]
            for msg in limited_history:
                # OpenAI 형식으로 변환 (user/assistant)
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                # 메시지 길이 제한 (200자 이상이면 축약)
                if len(content) > 200:
                    content = content[:200] + "..."
                messages.append({
                    "role": role,
                    "content": content
                })
        
        # 3. 현재 사용자 입력 추가
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 디버깅: 프롬프트 구성 확인
        if messages:
            total_length = sum(len(str(m.get("content", ""))) for m in messages)
        
        # API 호출
        openai_client = get_openai_client()
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        
        # 응답 추출
        response_text = response.choices[0].message.content
        
        
        return response_text

    except Exception as e:
        import traceback
        return f"오류가 발생했습니다: {str(e)}"


#========================================================================================================
# 헬퍼 함수들 (RAG 포맷팅 등 - 기존 코드와 호환성 유지)
#========================================================================================================

def _format_rag_solution(rag_solution: dict) -> str:
    """
    RAG 솔루션 검색 결과를 LLM이 이해하기 쉬운 형식으로 포맷팅
    """
    formatted_parts = []
    
    diagnosis = rag_solution.get("diagnosis", "")
    if diagnosis:
        formatted_parts.append(f"### 확정 질환명\n{diagnosis}\n")
    
    evidence = rag_solution.get("evidence", [])
    if evidence:
        formatted_parts.append(f"### 솔루션 및 치료 정보\n")
        for idx, ev in enumerate(evidence, 1):
            text = ev.get("text", "")
            metadata = ev.get("metadata", {})
            page = metadata.get("page", "N/A")
            section = metadata.get("section", "N/A")
            
            if text:
                formatted_parts.append(f"#### 정보 {idx} (페이지 {page}, 섹션: {section})")
                formatted_parts.append(text)
                formatted_parts.append("")
    else:
        formatted_parts.append("### 솔루션 및 치료 정보\n(관련 정보를 찾을 수 없습니다.)")
    
    return "\n".join(formatted_parts)


def _format_rag_hypothesis_result(rag_result: dict) -> str:
    """
    RAG Hypothesis 검색 결과를 포맷팅
    """
    formatted_parts = []
    
    input_symptom = rag_result.get("input_symptom", "")
    if input_symptom:
        formatted_parts.append(f"### 입력 증상\n{input_symptom}\n")
    
    diagnosis_candidates = rag_result.get("diagnosis_candidates", [])
    if diagnosis_candidates:
        formatted_parts.append(f"### 검색된 질환 후보 (Top {len(diagnosis_candidates)})\n")
        for idx, diag in enumerate(diagnosis_candidates, 1):
            formatted_parts.append(f"{idx}. {diag}")
        formatted_parts.append("")
    
    by_diagnosis = rag_result.get("by_diagnosis", {})
    if by_diagnosis:
        formatted_parts.append("### 각 질환별 진단 기준\n")
        for diag, criteria_list in by_diagnosis.items():
            if criteria_list and len(criteria_list) > 0:
                formatted_parts.append(f"#### {diag}")
                for criteria in criteria_list:
                    text = criteria.get("text", "")
                    metadata = criteria.get("metadata", {})
                    page = metadata.get("page", "N/A")
                    
                    if text:
                        formatted_parts.append(f"**진단 기준 (페이지 {page}):**")
                        formatted_parts.append(text)
                        formatted_parts.append("")
            else:
                formatted_parts.append(f"#### {diag}")
                formatted_parts.append("(진단 기준 정보 없음)")
                formatted_parts.append("")
    
    return "\n".join(formatted_parts)


def _format_by_diagnosis(by_diagnosis: dict) -> str:
    """
    Stage 3에서 사용하는 '깨끗한 진단 기준(by_diagnosis)'만을 포맷팅
    """
    if not isinstance(by_diagnosis, dict):
        return ""
    
    formatted_parts = ["### 각 질환별 진단 기준"]
    for diag, criteria_list in by_diagnosis.items():
        formatted_parts.append(f"#### {diag}")
        if criteria_list and isinstance(criteria_list, list):
            for criteria in criteria_list:
                if not isinstance(criteria, dict):
                    continue
                text = criteria.get("text", "")
                metadata = criteria.get("metadata", {}) or {}
                page = metadata.get("page", "N/A")
                if text:
                    formatted_parts.append(f"**진단 기준 (페이지 {page}):**")
                    formatted_parts.append(text)
                    formatted_parts.append("")
        else:
            formatted_parts.append("(진단 기준 정보 없음)")
            formatted_parts.append("")
    return "\n".join(formatted_parts)


def ask_openai_with_stage(
    user_input: str,
    prompt_template: str,
    context_data: dict,
    conversation_history: list = None,
    previous_stage_data: dict = None,
    model: str = None
) -> str:
    """
    단계별 프롬프트와 컨텍스트를 사용하여 OpenAI API 호출
    """
    try:
        model_name = model or DEFAULT_MODEL
        
        # Context를 문자열로 변환
        context_str = ""
        if context_data:
            context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        
        # 이전 단계 데이터 포함
        input_section = ""
        if previous_stage_data:
            if isinstance(previous_stage_data, dict) and "stage1_summary" in previous_stage_data:
                stage1_summary = previous_stage_data.get("stage1_summary", "")
                stage3_validation = previous_stage_data.get("stage3_validation", "")
                
                rag_solution = previous_stage_data.get("rag_solution")
                if rag_solution:
                    solution_formatted = _format_rag_solution(rag_solution)
                    input_section = f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}\n\n## RAG Solution Results\n{solution_formatted}" if stage1_summary else f"{stage3_validation}\n\n## RAG Solution Results\n{solution_formatted}"
                else:
                    input_section = f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}" if stage1_summary else stage3_validation
            elif isinstance(previous_stage_data, dict):
                if "by_diagnosis" in previous_stage_data:
                    bydiag = previous_stage_data.get("by_diagnosis") or {}
                    bydiag_formatted = _format_by_diagnosis(bydiag)
                    hypothesis_report = previous_stage_data.get("hypothesis_report", "")
                    hypothesis_content = hypothesis_report
                    if hypothesis_report and "Hypothesis String:" in hypothesis_report:
                        hypothesis_content = hypothesis_report.split("Hypothesis String:", 1)[1].strip()
                    input_section = f"## Hypothesis String\n{hypothesis_content}\n\n## RAG Search Results\n{bydiag_formatted}"
                elif "rag_result" in previous_stage_data:
                    rag_result = previous_stage_data.get("rag_result")
                    if rag_result:
                        rag_formatted = _format_rag_hypothesis_result(rag_result)
                        input_section = rag_formatted
                        summary_report = previous_stage_data.get("summary_report", "")
                        if summary_report:
                            if "Summary String:" in summary_report:
                                summary_content = summary_report.split("Summary String:", 1)[1].strip()
                            else:
                                summary_content = summary_report
                            input_section = f"## Summary String\n{summary_content}\n\n## RAG Search Results\n{rag_formatted}"
                        else:
                            hypothesis_report = previous_stage_data.get("hypothesis_report", "")
                            if hypothesis_report:
                                if "Hypothesis String:" in hypothesis_report:
                                    hypothesis_content = hypothesis_report.split("Hypothesis String:", 1)[1].strip()
                                else:
                                    hypothesis_content = hypothesis_report
                                input_section = f"## Hypothesis String\n{hypothesis_content}\n\n## RAG Search Results\n{rag_formatted}"
                else:
                    for key in ["summary_report", "hypothesis_report", "validation_result"]:
                        if key in previous_stage_data:
                            input_section = previous_stage_data[key]
                            break
                    if not input_section:
                        input_section = json.dumps(previous_stage_data, ensure_ascii=False, indent=2)
            else:
                input_section = str(previous_stage_data)
        
        # 프롬프트 구성
        full_prompt = f"""{prompt_template}

## Required Context Data
{context_str if context_str else "(없음)"}

{input_section if input_section else ""}

## Current User Input
User: {user_input}

Assistant:"""
        
        # 대화 히스토리 변환
        history_text = ""
        if conversation_history:
            history_text = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in conversation_history[-10:]
            ])
        
        # OpenAI 메시지 형식으로 구성
        messages = []
        
        # 시스템 메시지 (프롬프트 + 컨텍스트)
        system_content = full_prompt
        if history_text:
            system_content += f"\n\n## Conversation History\n{history_text}"
        
        messages.append({
            "role": "system",
            "content": system_content
        })
        
        # 사용자 입력
        messages.append({
            "role": "user",
            "content": user_input
        })
        
        
        # API 호출
        openai_client = get_openai_client()
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content
        
        
        return response_text

    except Exception as e:
        import traceback
        return f"오류가 발생했습니다: {str(e)}"

