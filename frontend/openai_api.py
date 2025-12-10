import os
import json
from typing import List, Dict, Optional, Any
from openai import OpenAI
from dotenv import load_dotenv
from .context_handler import get_context

# 환경 변수 로드 및 OpenAI 클라이언트 초기화
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY가 환경 변수에 설정되지 않았습니다. .env 파일을 확인해주세요."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


def _normalize_history(conversation_history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """
    OpenAI chat 포맷에 맞게 히스토리를 정규화합니다.
    - 기존 코드에서 사용하던 'model' 역할을 'assistant'로 변환
    """
    if not conversation_history:
        return []

    normalized = []
    for msg in conversation_history:
        role = msg.get("role")
        if role == "model":
            role = "assistant"
        if role not in {"user", "assistant", "system", "tool", "function"}:
            role = "user"
        normalized.append({"role": role, "content": msg.get("content", "")})
    return normalized


def _run_chat(messages: List[Dict[str, str]]) -> str:
    response = client.chat.completions.create(model=DEFAULT_MODEL, messages=messages)
    return response.choices[0].message.content


def _log_prompt(stage: str, sources: List[str], user_input: str, history_len: int) -> None:
    """
    콘솔에 참조한 파일명만 출력합니다.
    """
    print(
        f"[LLM][{stage}] sources={sources if sources else 'N/A'}, "
        f"history={history_len}, user_len={len(user_input)}"
    )


def ask_openai(
    user_input: str,
    context: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    context_file: Optional[str] = None,
    stage_name: Optional[str] = None,
    context_sources: Optional[List[str]] = None,
) -> str:
    """
    사용자 입력을 받아 OpenAI ChatCompletion을 호출합니다.
    """
    try:
        if context is None and context_file is not None:
            context = get_context(context_file)
        elif context is None:
            context = get_context()

        messages = []
        if context:
            messages.append({"role": "system", "content": context})

        messages.extend(_normalize_history(conversation_history))
        messages.append({"role": "user", "content": user_input})

        stage = stage_name or "generic"
        _log_prompt(stage, context_sources or [], user_input, len(conversation_history or []))

        return _run_chat(messages)
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"


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
        formatted_parts.append("### 솔루션 및 치료 정보\n")
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
    RAG Hypothesis 검색 결과를 LLM이 이해하기 쉬운 형식으로 포맷팅
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
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    previous_stage_data: Optional[dict] = None,
    stage_name: Optional[str] = None,
    context_sources: Optional[List[str]] = None,
) -> str:
    """
    단계별 프롬프트와 컨텍스트를 사용하여 OpenAI ChatCompletion을 호출
    """
    try:
        context_str = ""
        if context_data:
            context_str = json.dumps(context_data, ensure_ascii=False, indent=2)

        input_section = ""
        if previous_stage_data:
            if isinstance(previous_stage_data, dict) and "stage1_summary" in previous_stage_data:
                stage1_summary = previous_stage_data.get("stage1_summary", "")
                stage3_validation = previous_stage_data.get("stage3_validation", "")

                rag_solution = previous_stage_data.get("rag_solution")
                if rag_solution:
                    solution_formatted = _format_rag_solution(rag_solution)
                    input_section = (
                        f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}\n\n## RAG Solution Results\n{solution_formatted}"
                        if stage1_summary
                        else f"{stage3_validation}\n\n## RAG Solution Results\n{solution_formatted}"
                    )
                else:
                    input_section = (
                        f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}"
                        if stage1_summary
                        else stage3_validation
                    )
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

        system_prompt = f"""{prompt_template}

## Required Context Data
{context_str if context_str else "(없음)"}

{input_section if input_section else ""}
"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(_normalize_history(conversation_history))
        messages.append({"role": "user", "content": user_input})

        stage = stage_name or "stage-flow"
        _log_prompt(stage, context_sources or [], user_input, len(conversation_history or []))

        return _run_chat(messages)
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"
