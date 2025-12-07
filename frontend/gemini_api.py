import os  # 운영체제 다루는 기본 모듈 , .env파일 불러올때 사용함
import json
import google.generativeai as genai  # 제미나이 모델을 python에서 쓸 수 있게 해주는 공식 SDK
from dotenv import (
    load_dotenv,
)  # 파일 안에 적힌 환경 변수들을 프로그램 실행 시 자동으로 불러오는 역할
from .context_handler import get_context

# 환경 변수 로드
load_dotenv()
# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# GEMINI_API_KEY가 환경 변수에 설정되어 있는지 확인
if GEMINI_API_KEY:
    genai.configure(api_key="")
else:
    raise ValueError(
        "GEMINI_API_KEY가 환경 변수에 설정되지 않았습니다. .env 파일을 확인해주세요."
    )

#========================================================================================================
# ask_gemnini()함수 정의 / 사용자 질문 -> Gemini API 호출 -> 응답 반환
# Gemini API를 호출하여 응답을 생성합니다.

# Args:
#     user_input: 사용자 입력 메시지
#     context : 추가 컨텍스트 (RAG 검색 결과 등)
#     conversation_history: 대화 히스토리 리스트
#     context_file: 컨텍스트 파일 이름

# Returns:
#     Gemini의 응답 텍스트
#========================================================================================================

def ask_gemini(
    user_input: str, context: str = None, conversation_history: list = None, context_file: str = None
) -> str:
    try:
        # 모델 초기화
        model = genai.GenerativeModel("gemini-2.5-flash")

        # 컨텍스트 처리: context 파라미터가 없으면 파일에서 로드
        if context is None and context_file is not None:
            context = get_context(context_file)
        elif context is None:
            # 기본 context 파일 사용 (context_file이 명시되지 않은 경우에만)
            pass

        # 프롬프트 구성 (context와 conversation_history를 모두 포함)
        prompt_parts = []

        # 1. 컨텍스트가 있으면 먼저 추가 (시스템 지시사항, 프롬프트 등)
        if context:
            prompt_parts.append(context)

        # 2. 대화 히스토리가 있으면 추가 (각 단계별로 필요한 만큼만)
        if conversation_history:
            # 히스토리 길이 제한 (최대 10개 메시지 = 5쌍)
            limited_history = conversation_history[-10:]
            history_text = "\n".join(
                [
                    f"{'사용자' if msg['role'] == 'user' else '상담사'}: {msg['content'][:200]}..." if len(msg['content']) > 200 else f"{'사용자' if msg['role'] == 'user' else '상담사'}: {msg['content']}"
                    for msg in limited_history
                ]
            )
            prompt_parts.append(f"## 이전 대화 기록 (최근 {len(limited_history)}개 메시지)\n{history_text}\n")

        # 3. 현재 사용자 입력 추가
        prompt_parts.append(f"## 현재 사용자 입력\n{user_input}")

        # 최종 프롬프트 조합
        if len(prompt_parts) > 1:
            prompt = "\n\n".join(prompt_parts)
        else:
            prompt = user_input

        # 디버깅: 프롬프트 구성 확인
        print(f"[Gemini API] 프롬프트 구성 완료:")
        print(f"  - 전체 길이: {len(prompt)} 문자")
        print(f"  - 컨텍스트 포함: {'예' if context else '아니오'}")
        print(f"  - 히스토리 포함: {'예' if conversation_history else '아니오'} (최근 {len(conversation_history) if conversation_history else 0}개 메시지)")
        print(f"  - 프롬프트 미리보기 (처음 300자):\n{prompt[:300]}...")

        # API 호출
        response = model.generate_content(prompt)

        print(f"[Gemini API] 응답 수신 완료 (길이: {len(response.text)} 문자)")

        return response.text

    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"


#========================================================================================================
# ask_gemini_with_stage()함수 정의 / 단계별 프롬프트와 컨텍스트를 사용하여 Gemini API 호출
# 단계별 상담 프로세스에서 사용하는 함수

# Args:
#     user_input: 사용자 입력 메시지
#     prompt_template: 단계별 프롬프트 템플릿 (마크다운)
#     context_data: 단계별 context JSON 데이터
#     conversation_history: 대화 히스토리 리스트
#     previous_stage_data: 이전 단계의 출력 데이터 (선택적)

# Returns:
#     Gemini의 응답 텍스트
#========================================================================================================

def _format_rag_solution(rag_solution: dict) -> str:
    """
    RAG 솔루션 검색 결과를 Gemini가 이해하기 쉬운 형식으로 포맷팅
    
    Args:
        rag_solution: RAG 솔루션 API 응답 딕셔너리
    
    Returns:
        포맷팅된 문자열
    """
    formatted_parts = []
    
    # 확정 질환명
    diagnosis = rag_solution.get("diagnosis", "")
    if diagnosis:
        formatted_parts.append(f"### 확정 질환명\n{diagnosis}\n")
    
    # 솔루션 증거
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
    RAG Hypothesis 검색 결과를 Gemini가 이해하기 쉬운 형식으로 포맷팅
    
    Args:
        rag_result: RAG Hypothesis API 응답 딕셔너리
    
    Returns:
        포맷팅된 문자열
    """
    formatted_parts = []
    
    # 입력 증상
    input_symptom = rag_result.get("input_symptom", "")
    if input_symptom:
        formatted_parts.append(f"### 입력 증상\n{input_symptom}\n")
    
    # 질환 후보
    diagnosis_candidates = rag_result.get("diagnosis_candidates", [])
    if diagnosis_candidates:
        formatted_parts.append(f"### 검색된 질환 후보 (Top {len(diagnosis_candidates)})\n")
        for idx, diag in enumerate(diagnosis_candidates, 1):
            formatted_parts.append(f"{idx}. {diag}")
        formatted_parts.append("")
    
    # 각 질환별 진단 기준
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


def ask_gemini_with_stage(
    user_input: str,
    prompt_template: str,
    context_data: dict,
    conversation_history: list = None,
    previous_stage_data: dict = None
) -> str:
    """
    단계별 프롬프트와 컨텍스트를 사용하여 Gemini API 호출
    
    Args:
        user_input: 사용자 입력
        prompt_template: 단계별 프롬프트 템플릿 (마크다운)
        context_data: 단계별 context JSON 데이터 (여러 파일이 통합된 dict)
        conversation_history: 대화 히스토리
        previous_stage_data: 이전 단계의 출력 데이터 (다음 단계 입력으로 활용)
    """
    try:
        # 모델 초기화
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Context를 문자열로 변환 (여러 파일이 통합된 경우)
        context_str = ""
        if context_data:
            context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
        
        # 대화 히스토리 포함
        history_text = ""
        if conversation_history:
            history_text = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in conversation_history[-10:]  # 최근 10개 포함
            ])
        
        # 이전 단계 데이터 포함 (이전 단계의 출력 문자열 추출)
        input_section = ""
        if previous_stage_data:
            # Stage 4는 Stage 1과 Stage 3의 데이터를 모두 받음
            if isinstance(previous_stage_data, dict) and "stage1_summary" in previous_stage_data:
                # Stage 4: Stage 1의 Summary String과 Stage 3의 Validated String 모두 포함
                stage1_summary = previous_stage_data.get("stage1_summary", "")
                stage3_validation = previous_stage_data.get("stage3_validation", "")
                
                # RAG 솔루션 결과가 있으면 포함
                rag_solution = previous_stage_data.get("rag_solution")
                if rag_solution:
                    solution_formatted = _format_rag_solution(rag_solution)
                    input_section = f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}\n\n## RAG Solution Results\n{solution_formatted}" if stage1_summary else f"{stage3_validation}\n\n## RAG Solution Results\n{solution_formatted}"
                else:
                    input_section = f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}" if stage1_summary else stage3_validation
            elif isinstance(previous_stage_data, dict):
                # Stage 3 전용: by_diagnosis가 있으면 이를 참고 자료로 포함
                if "by_diagnosis" in previous_stage_data:
                    bydiag = previous_stage_data.get("by_diagnosis") or {}
                    bydiag_formatted = _format_by_diagnosis(bydiag)
                    hypothesis_report = previous_stage_data.get("hypothesis_report", "")
                    hypothesis_content = hypothesis_report
                    if hypothesis_report and "Hypothesis String:" in hypothesis_report:
                        hypothesis_content = hypothesis_report.split("Hypothesis String:", 1)[1].strip()
                    # Hypothesis String + 각 질환별 진단 기준
                    input_section = f"## Hypothesis String\n{hypothesis_content}\n\n## RAG Search Results\n{bydiag_formatted}"
                    print(f"[Gemini API] Stage 3 input_section 생성 완료 (Hypothesis String + by_diagnosis)")
                    print(f"  - Hypothesis String 길이: {len(hypothesis_content or '')} 문자")
                    print(f"  - by_diagnosis 길이: {len(bydiag_formatted or '')} 문자")
                    print(f"  - 전체 input_section 길이: {len(input_section)} 문자")
                # (Stage 2 내부용) RAG Hypothesis 전체 결과가 있으면 그대로 포맷팅
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
                                print(f"[Gemini API] Stage 3 input_section 생성 완료 (Hypothesis String + RAG Search Results)")
                                print(f"  - Hypothesis String 길이: {len(hypothesis_content)} 문자")
                                print(f"  - RAG Search Results 길이: {len(rag_formatted)} 문자")
                                print(f"  - 전체 input_section 길이: {len(input_section)} 문자")
                else:
                    # RAG 결과가 없으면 기존 로직대로 처리
                    for key in ["summary_report", "hypothesis_report", "validation_result"]:
                        if key in previous_stage_data:
                            input_section = previous_stage_data[key]
                            break
                    # 만약 위 키가 없으면 전체를 JSON으로 표시
                    if not input_section:
                        input_section = json.dumps(previous_stage_data, ensure_ascii=False, indent=2)
            else:
                input_section = str(previous_stage_data)
        
        # 최종 input_section 확인 (Stage 3 디버깅용)
        if input_section:
            print(f"[Gemini API] 최종 input_section 미리보기 (처음 500자):")
            print(f"{input_section[:500]}...")
        
        full_prompt = f"""{prompt_template}

## Required Context Data
{context_str if context_str else "(없음)"}

{input_section if input_section else ""}

## Conversation History
{history_text if history_text else "(대화 시작)"}

## Current User Input
User: {user_input}

Assistant:"""
        
        # 프롬프트 길이 로그
        print(f"[Gemini API] 프롬프트 길이: {len(full_prompt)} 문자")
        print(f"[Gemini API] API 호출 시작...")
        
        # API 호출
        response = model.generate_content(full_prompt)
        
        print(f"[Gemini API] 응답 수신 완료, 길이: {len(response.text)} 문자")
        print(f"[Gemini API] 응답 미리보기: {response.text[:200]}...")
        
        return response.text

    except Exception as e:
        print(f"[Gemini API] 오류 발생: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[Gemini API] 상세 에러:\n{traceback.format_exc()}")
        return f"오류가 발생했습니다: {str(e)}"






