import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file


def severity_node(state: CounselingState) -> Dict[str, Any]:
    """
    Severity Stage (4단계) 처리 노드
    - 확정된 1개 질환에 대한 심각도 평가 수행
    - 1턴: 질환/컨텍스트 기반으로 심각도 질문 리스트 전체 생성 (LLM 1회 호출)
    - 2턴~: 생성된 질문을 순차적으로 소모하며 1~5점 응답 수집 (코드에서 직접 진행)
    - 마지막: 모든 응답을 모아 최종 심각도 평가 결과 도출 (LLM 별도 1회 호출)
    """

    messages = state["messages"]

    # 최신 HumanMessage를 찾아 사용자 입력으로 사용
    user_input = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_input = msg.content or ""
            break

    # 1. 확정된 질환명 확인
    target_diagnosis = state.get("severity_diagnosis")
    if not target_diagnosis:
        return {
            "messages": [
                AIMessage(content="오류: 심각도 평가 대상 질환이 설정되지 않았습니다.")
            ]
        }

    # 2. 질환별 심각도 Context 동적 로드 시도
    disease_context = ""
    try:
        disease_key = target_diagnosis.split()[0].lower()  # 첫 단어 사용

        mapping = {
            "depressive": "depression.json",
            "depression": "depression.json",
            "anxiety": "anxiety.json",
            "bipolar": "bipolar.json",
            "schizophrenia": "schizophrenia.json",
            "adhd": "adhd.json",
            "ocd": "ocd.json",
            "panic": "anxiety.json",  # 예시
            "substance": "substance.json",
        }

        filename = mapping.get(disease_key)
        if not filename:
            filename = f"{disease_key}.json"

        loaded_context = load_context_from_file(f"diseases/{filename}")
        if loaded_context:
            disease_context = loaded_context
        else:
            disease_context = (
                "(해당 질환의 특화된 심각도 척도 파일이 없어, "
                "일반적인 증상 강도와 빈도를 기준으로 평가합니다.)"
            )

    except Exception as e:
        print(f"심각도 컨텍스트 로드 오류: {e}")
        disease_context = "(심각도 컨텍스트 로드 실패)"

    # 3. 프롬프트 / 공통 Context 로드
    prompt_path = Path("prompts/stage4_severity.md")
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        else:
            base_prompt = "기본 프롬프트 로드 실패"
    except Exception as e:
        base_prompt = f"프롬프트 로드 오류: {e}"

    common_severity_context = load_context_from_file(
        "stage_specific/context_stage4_severity.json"
    )

    # 4. 심각도 질문/응답용 내부 상태
    severity_questions: List[Dict[str, Any]] = state.get("severity_questions") or []
    current_index: int = state.get("severity_current_index", 0)
    answers: List[int] = state.get("severity_answers") or []

    print(
        f"[Severity Debug] questions_in_state={len(severity_questions)}, "
        f"current_index={current_index}, answers_len={len(answers)}, "
        f"target_diagnosis={target_diagnosis}"
    )

    def build_question_message(
        question_text: str,
        *,
        is_first: bool,
        question_index: int,
        total_questions: int,
    ) -> str:
        """
        사용자에게 보여줄 질문 포맷.
        - 첫 질문에서는 튜토리얼/안내 멘트를 충분히 제공
        - 이후 질문에서는 심플하게 현재 번호만 표시
        """
        scale_text = (
            "1. 전혀 그렇지 않다\n"
            "2. 거의 그렇지 않다\n"
            "3. 가끔 그렇다\n"
            "4. 자주 그렇다\n"
            "5. 매우 자주/항상 그렇다"
        )

        if is_first:
            return (
                f"이제 4단계(심각도 평가)를 진행할게요. 평가 대상 질환은 `{target_diagnosis}` 입니다.\n"
                "아래 질문들에 대해, **요즘 상태에 가장 가까운 번호(1~5)** 를 숫자로만 입력해 주세요.\n\n"
                "[응답 방법 튜토리얼]\n"
                "- 1: 거의 해당되지 않는다 / 드물게 그렇다\n"
                "- 3: 가끔 그렇다 / 어느 정도 해당된다\n"
                "- 5: 매우 자주 그렇다 / 거의 항상 그렇다\n"
                "예를 들어, '가끔 있는 것 같다'면 3을, '거의 매일 그렇다'면 5에 가깝게 선택해 주세요.\n\n"
                f"[질문 {question_index}/{total_questions}]\n"
                f"질문: {question_text}\n\n"
                f"{scale_text}"
            )

        return (
            f"[질문 {question_index}/{total_questions}]\n"
            f"질문: {question_text}\n\n"
            f"{scale_text}"
        )

    # 5-1. 아직 질문 리스트가 없는 경우 → LLM으로 전체 질문 생성
    if not severity_questions:
        print("[Severity Debug] 질문 리스트 없음 → LLM으로 새로 생성")
        system_instructions = f"""
{base_prompt}

## 평가 대상 질환: {target_diagnosis}

## 질환별 심각도 척도 정보
{disease_context}

## 공통 가이드라인
{common_severity_context}

## 안내
- 지금은 '질문 생성 모드'입니다.
- 사용자에게는 자연스러운 안내 문장만 보여 주고, 실제 질문 리스트는 INTERNAL_DATA 섹션에 JSON으로만 제공하세요.

---INTERNAL_DATA---
Questions JSON: {{"questions": [{{"id": "s1", "text": "...", "related_symptom": "..."}}]}}
"""

        response_text = ask_openai(
            user_input=f"{target_diagnosis}에 대한 심각도 평가를 위한 전체 질문 리스트를 생성해주세요.",
            context=system_instructions,
            conversation_history=None,
        )

        internal_data = ""
        if "---INTERNAL_DATA---" in response_text:
            parts = response_text.split("---INTERNAL_DATA---", 1)
            internal_data = parts[1].strip()

        questions: List[Dict[str, Any]] = []
        if "Questions JSON:" in internal_data:
            try:
                q_str = internal_data.split("Questions JSON:", 1)[1].strip()
                questions_json = json.loads(q_str)
                if isinstance(questions_json, dict) and isinstance(
                    questions_json.get("questions"), list
                ):
                    questions = questions_json["questions"]
            except Exception as e:
                print(f"Severity Questions JSON 파싱 오류: {e}")

        if not questions:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "오류: 심각도 평가용 질문을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."
                        )
                    )
                ]
            }

        first_question = questions[0].get("text", "첫 번째 질문을 불러오지 못했습니다.")
        total_q = len(questions)

        print(
            f"[Severity Debug] 질문 생성 완료: total_questions={total_q}. "
            "State에 severity_questions 저장 후 첫 질문 반환."
        )

        return {
            "messages": [
                AIMessage(
                    content=build_question_message(
                        first_question,
                        is_first=True,
                        question_index=1,
                        total_questions=total_q,
                    )
                )
            ],
            "severity_questions": questions,
            "severity_current_index": 0,
            "severity_answers": [],
        }

    # 5-2. 질문 리스트는 이미 있고, 사용자 답변(1~5)을 받아 다음 질문으로 진행
    total_q = len(severity_questions)

    # 사용자 입력에서 1~5 사이 숫자 추출
    answer_value: Optional[int] = None
    if user_input:
        match = re.search(r"[1-5]", user_input)
        if match:
            try:
                answer_value = int(match.group(0))
            except ValueError:
                answer_value = None

    if answer_value is None:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "답변을 이해하지 못했어요. 1, 2, 3, 4, 5 중 하나의 숫자로 "
                        "현재 상태에 가장 가까운 정도를 입력해 주세요."
                    )
                )
            ]
        }

    # 현재 질문에 대한 답변 저장
    if len(answers) <= current_index:
        answers.append(answer_value)
    else:
        answers[current_index] = answer_value

    current_index += 1

    print(
        f"[Severity Debug] 응답 수신: answer={answer_value}, "
        f"next_index={current_index}/{total_q}"
    )

    # 아직 남은 질문이 있다면 → 다음 질문 출력 (LLM 재호출 없음)
    if current_index < total_q:
        next_q = severity_questions[current_index]
        next_text = next_q.get("text", "다음 질문을 불러오지 못했습니다.")
        print(
            f"[Severity Debug] 다음 질문 진행: index={current_index}, "
            f"text_preview={next_text[:30]}"
        )
        return {
            "messages": [
                AIMessage(
                    content=build_question_message(
                        next_text,
                        is_first=False,
                        question_index=current_index + 1,
                        total_questions=total_q,
                    )
                )
            ],
            "severity_questions": severity_questions,
            "severity_current_index": current_index,
            "severity_answers": answers,
        }

    # 5-3. 모든 질문에 답변이 완료된 경우 → LLM으로 최종 심각도 평가 수행
    print(
        "[Severity Debug] 모든 질문에 대한 응답 완료 → "
        "평가용 LLM 호출 (Severity Result 계산)"
    )
    eval_instructions = f"""
{base_prompt}

## 평가 대상 질환: {target_diagnosis}

## 질환별 심각도 척도 정보
{disease_context}

## 공통 가이드라인
{common_severity_context}

## 심각도 평가용 질문 리스트
{json.dumps(severity_questions, ensure_ascii=False, indent=2)}

## 사용자 응답 (각 질문에 대한 1~5 점수, 질문 순서대로)
{json.dumps(answers, ensure_ascii=False, indent=2)}

## 지시사항
- 위 질문과 응답을 기반으로 심각도 평가를 수행하세요.
- 평가 결과 텍스트 요약을 작성하고, INTERNAL_DATA 섹션에 아래 형식으로 포함하세요.

---INTERNAL_DATA---
Severity Result String: [심각도 평가 결과 텍스트 요약]
Severity JSON: {{"diagnosis": "{target_diagnosis}", "level": "...", "score": "..."}}
"""

    eval_response = ask_openai(
        user_input="위 데이터를 바탕으로 심각도 평가 결과를 정리해 주세요.",
        context=eval_instructions,
        conversation_history=None,
    )

    user_message = eval_response
    internal_data = ""
    new_state: Dict[str, Any] = {
        "severity_questions": severity_questions,
        "severity_current_index": current_index,
        "severity_answers": answers,
    }

    if "---INTERNAL_DATA---" in eval_response:
        parts = eval_response.split("---INTERNAL_DATA---", 1)
        user_message = parts[0].strip()
        internal_data = parts[1].strip()

    if "Severity Result String:" in internal_data:
        result_string = (
            internal_data.split("Severity Result String:", 1)[1]
            .split("Severity JSON:", 1)[0]
            .strip()
        )
        new_state["severity_result_string"] = result_string

    # 필요 시 Severity JSON도 추가 파싱 가능

    return {
        "messages": [AIMessage(content=user_message)],
        **new_state,
    }

