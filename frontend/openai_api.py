import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from .context_handler import get_context

# 환경 변수 로드
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY = 10

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY가 환경 변수에 설정되지 않았습니다. .env 파일을 확인해주세요."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


def _normalize_history(
    history: Optional[List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    """
    이전 대화 히스토리를 OpenAI Chat 형식으로 변환.
    'model', 'assistant', 'ai'는 assistant로, 나머지는 user로 매핑합니다.
    """
    if not history:
        return []

    normalized: List[Dict[str, str]] = []
    for msg in history[-MAX_HISTORY:]:
        role = msg.get("role", "user")
        role = "assistant" if role in {"assistant", "model", "ai"} else "user"
        content = msg.get("content", "")
        if content is None:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _format_rag_solution(rag_solution: dict) -> str:
    """RAG 솔루션 결과를 사람이 읽기 쉬운 문자열로 포맷."""
    if not isinstance(rag_solution, dict):
        return ""

    parts: List[str] = []
    diagnosis = rag_solution.get("diagnosis", "")
    if diagnosis:
        parts.append(f"### 확정 질환명\n{diagnosis}\n")

    evidence = rag_solution.get("evidence", [])
    if evidence:
        parts.append("### 솔루션 및 치료 정보\n")
        for idx, ev in enumerate(evidence, 1):
            text = ev.get("text", "")
            metadata = ev.get("metadata", {}) or {}
            page = metadata.get("page", "N/A")
            section = metadata.get("section", "N/A")
            if text:
                parts.append(f"#### 정보 {idx} (페이지 {page}, 섹션: {section})")
                parts.append(text)
                parts.append("")
    else:
        parts.append("### 솔루션 및 치료 정보\n(관련 정보를 찾을 수 없습니다.)")

    return "\n".join(parts)


def _format_rag_hypothesis_result(rag_result: dict) -> str:
    """RAG Hypothesis 검색 결과 포맷."""
    if not isinstance(rag_result, dict):
        return ""

    parts: List[str] = []
    input_symptom = rag_result.get("input_symptom", "")
    if input_symptom:
        parts.append(f"### 입력 증상\n{input_symptom}\n")

    diagnosis_candidates = rag_result.get("diagnosis_candidates", [])
    if diagnosis_candidates:
        parts.append(f"### 검색된 질환 후보 (Top {len(diagnosis_candidates)})\n")
        for idx, diag in enumerate(diagnosis_candidates, 1):
            parts.append(f"{idx}. {diag}")
        parts.append("")

    by_diagnosis = rag_result.get("by_diagnosis", {})
    if by_diagnosis:
        parts.append("### 각 질환별 진단 기준\n")
        for diag, criteria_list in by_diagnosis.items():
            if criteria_list and len(criteria_list) > 0:
                parts.append(f"#### {diag}")
                for criteria in criteria_list:
                    text = criteria.get("text", "")
                    metadata = criteria.get("metadata", {}) or {}
                    page = metadata.get("page", "N/A")
                    if text:
                        parts.append(f"**진단 기준 (페이지 {page}):**")
                        parts.append(text)
                        parts.append("")
            else:
                parts.append(f"#### {diag}")
                parts.append("(진단 기준 정보 없음)")
                parts.append("")

    return "\n".join(parts)


def _format_by_diagnosis(by_diagnosis: dict) -> str:
    """Stage 3용 진단 기준 포맷."""
    if not isinstance(by_diagnosis, dict):
        return ""

    parts: List[str] = ["### 각 질환별 진단 기준"]
    for diag, criteria_list in by_diagnosis.items():
        parts.append(f"#### {diag}")
        if criteria_list and isinstance(criteria_list, list):
            for criteria in criteria_list:
                if not isinstance(criteria, dict):
                    continue
                text = criteria.get("text", "")
                metadata = criteria.get("metadata", {}) or {}
                page = metadata.get("page", "N/A")
                if text:
                    parts.append(f"**진단 기준 (페이지 {page}):**")
                    parts.append(text)
                    parts.append("")
        else:
            parts.append("(진단 기준 정보 없음)")
            parts.append("")
    return "\n".join(parts)


def _chat(messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
    """OpenAI Chat Completion 호출 래퍼."""
    response = client.chat.completions.create(
        model=model or OPENAI_MODEL,
        messages=messages,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def ask_openai(
    user_input: str,
    context: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    context_file: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    OpenAI Chat API를 사용하여 응답을 생성합니다.

    Args:
        user_input: 사용자 입력 메시지
        context: 시스템/컨텍스트 프롬프트 문자열
        conversation_history: {'role': 'user'|'assistant', 'content': ...} 리스트
        context_file: context가 없을 때 불러올 파일 이름
        model: 사용할 모델 명 (미지정 시 OPENAI_MODEL 사용)
    """
    try:
        if context is None and context_file is not None:
            context = get_context(context_file)
        elif context is None:
            context = get_context()

        messages: List[Dict[str, str]] = []
        if context:
            messages.append({"role": "system", "content": context})

        messages.extend(_normalize_history(conversation_history))
        messages.append({"role": "user", "content": user_input})

        return _chat(messages, model=model)

    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"


def ask_openai_with_stage(
    user_input: str,
    prompt_template: str,
    context_data: dict,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    previous_stage_data: Optional[dict] = None,
    model: Optional[str] = None,
) -> str:
    """
    단계별 프롬프트와 컨텍스트를 사용하여 OpenAI Chat API 호출.
    """
    try:
        context_str = ""
        if context_data:
            context_str = json.dumps(context_data, ensure_ascii=False, indent=2)

        history_text = ""
        normalized_history = _normalize_history(conversation_history)
        if normalized_history:
            history_text = "\n".join(
                [f"{msg['role'].capitalize()}: {msg['content']}" for msg in normalized_history]
            )

        input_section = ""
        if previous_stage_data:
            if isinstance(previous_stage_data, dict) and "stage1_summary" in previous_stage_data:
                stage1_summary = previous_stage_data.get("stage1_summary", "")
                stage3_validation = previous_stage_data.get("stage3_validation", "")
                rag_solution = previous_stage_data.get("rag_solution")
                if rag_solution:
                    solution_formatted = _format_rag_solution(rag_solution)
                    input_section = (
                        f"{stage3_validation}\n\n## Stage 1 Summary (참고용)\n{stage1_summary}\n\n"
                        f"## RAG Solution Results\n{solution_formatted}"
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
                    input_section = (
                        f"## Hypothesis String\n{hypothesis_content}\n\n## RAG Search Results\n{bydiag_formatted}"
                    )
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
                                    hypothesis_content = hypothesis_report.split(
                                        "Hypothesis String:", 1
                                    )[1].strip()
                                else:
                                    hypothesis_content = hypothesis_report
                                input_section = (
                                    f"## Hypothesis String\n{hypothesis_content}\n\n## RAG Search Results\n{rag_formatted}"
                                )
                else:
                    for key in ["summary_report", "hypothesis_report", "validation_result"]:
                        if key in previous_stage_data:
                            input_section = previous_stage_data[key]
                            break
                    if not input_section:
                        input_section = json.dumps(previous_stage_data, ensure_ascii=False, indent=2)
            else:
                input_section = str(previous_stage_data)

        full_prompt = f"""{prompt_template}

## Required Context Data
{context_str if context_str else "(없음)"}

{input_section if input_section else ""}

## Conversation History
{history_text if history_text else "(대화 시작)"}

## Current User Input
User: {user_input}

Assistant:"""

        messages: List[Dict[str, str]] = [{"role": "system", "content": full_prompt}]
        messages.extend(normalized_history)
        messages.append({"role": "user", "content": user_input})

        return _chat(messages, model=model)

    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"
