import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_openai
from frontend.context_handler import load_context_from_file

def validation_node(state: CounselingState) -> Dict[str, Any]:
    """
    Validation Stage (3단계) 처리 노드
    - 의심 질환 검증을 위한 5지선다 질문 생성 및 응답 수집
    - 1턴: 질문 생성 (질환 기준 기반)
    - 2턴~: 사용자 응답 수집 및 진행
    - 마지막: 모든 답변 수집 후 확률 계산 및 결과 도출
    """
    messages = state['messages']

    # 최신 HumanMessage를 찾아 사용자 입력으로 사용
    user_input = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_input = msg.content or ""
            break
    
    # 상태 정보 가져오기
    hypothesis_criteria = state.get("hypothesis_criteria", [])
    if not hypothesis_criteria:
        return {
            "messages": [
                AIMessage(
                    content="오류: 가설 검증을 위한 기준 데이터가 없습니다. 상담을 초기화해주세요."
                )
            ]
        }

    # Validation 전용 상태
    validation_questions: List[Dict[str, Any]] = state.get("validation_questions") or []
    current_index: int = state.get("validation_current_index", 0)
    answers: List[int] = state.get("validation_answers") or []

    print(
        f"[Validation Debug] questions_in_state={len(validation_questions)}, "
        f"current_index={current_index}, answers_len={len(answers)}"
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
                "지금부터 3단계(가설 검증)를 진행할게요.\n"
                "아래 질문들에 대해, **요즘 상태에 가장 가까운 번호(1~5)** 를 숫자로만 입력해 주세요.\n\n"
                "[응답 방법 튜토리얼]\n"
                "- 1: 거의 해당되지 않는다 / 드물게 그렇다\n"
                "- 3: 가끔 그렇다 / 애매하지만 어느 정도 해당된다\n"
                "- 5: 매우 자주 그렇다 / 거의 항상 그렇다\n"
                "예를 들어, '조금 있는 것 같긴 한데 자주까지는 아닌 것 같다'면 3을, "
                "'거의 매일 그렇다'면 5에 가깝게 선택해 주세요.\n\n"
                f"[질문 {question_index}/{total_questions}]\n"
                f"질문: {question_text}\n\n"
                f"{scale_text}"
            )

        # 그 다음부터는 안내 멘트는 생략하고, 현재 질문 번호만 간단히 표시
        return (
            f"[질문 {question_index}/{total_questions}]\n"
            f"질문: {question_text}\n\n"
            f"{scale_text}"
        )

    # 1) 아직 질문 리스트가 없는 경우 → 한 번만 LLM으로 전체 질문 생성
    if not validation_questions:
        print("[Validation Debug] 질문 리스트 없음 → LLM으로 새로 생성")
        prompt_path = Path("prompts/stage3_validation.md")
        try:
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    base_prompt = f.read()
            else:
                base_prompt = "기본 프롬프트 로드 실패"
        except Exception as e:
            base_prompt = f"프롬프트 로드 오류: {e}"

        validation_context = load_context_from_file(
            "stage_specific/context_stage3_validation.json"
        )

        system_instructions = f"""
{base_prompt}

## 현재 상담 진행 상황
- **의심 질환 및 기준**:
{json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)}

## 출력 지침 (질문 생성 모드)
- 화면에 노출되는 영역에는 질문 리스트 JSON을 포함하지 마세요.
- 아래 INTERNAL_DATA 형식을 따라, 모든 질문 리스트를 JSON으로 제공하세요.

---INTERNAL_DATA---
Questions JSON: {{"questions": [{{"id": "q1", "text": "...", "target_diagnosis": "...", "related_criteria": "..."}}]}}
"""

        full_context = (
            f"{system_instructions}\n\n## Context Data\n{validation_context}"
        )

        response_text = ask_openai(
            user_input="Validation 단계를 위한 전체 질문 리스트를 생성해주세요.",
            context=full_context,
            conversation_history=None,
        )

        internal_data = ""
        if "---INTERNAL_DATA---" in response_text:
            parts = response_text.split("---INTERNAL_DATA---", 1)
            internal_data = parts[1].strip()

        questions: List[Dict[str, Any]] = []
        if "Questions JSON:" in internal_data:
            try:
                # INTERNAL_DATA 안에서 "Questions JSON:" 뒤에 나오는
                # 가장 바깥 { ... } 블록을 중괄호 깊이 계산으로 안전하게 추출
                start_pos = internal_data.index("Questions JSON:") + len(
                    "Questions JSON:"
                )
                substring = internal_data[start_pos:]

                # 코드블록이 있다면 먼저 건너뛰기 (```로 시작하는 경우)
                code_fence_index = substring.find("```")
                if code_fence_index != -1 and code_fence_index < substring.find("{"):
                    # ``` 이후부터 다시 탐색
                    substring = substring[code_fence_index + 3 :]

                brace_start = substring.find("{")
                if brace_start == -1:
                    print(
                        "[Validation Debug] Questions JSON 뒤에서 여는 중괄호를 찾지 못했습니다."
                    )
                else:
                    depth = 0
                    end_idx: Optional[int] = None
                    for i, ch in enumerate(substring[brace_start:]):
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                end_idx = brace_start + i
                                break
                    if end_idx is None:
                        print(
                            "[Validation Debug] Questions JSON 중괄호 블록이 닫히지 않았습니다."
                        )
                    else:
                        q_str = substring[brace_start : end_idx + 1].strip()
                        # 혹시 뒤에 ```가 붙어 있다면 제거
                        if q_str.endswith("```"):
                            q_str = q_str.rsplit("```", 1)[0].strip()

                        questions_json = json.loads(q_str)
                        if isinstance(questions_json, dict) and isinstance(
                            questions_json.get("questions"), list
                        ):
                            questions = questions_json["questions"]
                        else:
                            print(
                                "[Validation Debug] Questions JSON 구조가 예상과 다릅니다: "
                                f"type={type(questions_json)}"
                            )
            except Exception as e:
                print(f"Validation Questions JSON 파싱 오류: {e}")

        if not questions:
            # 질문 생성 실패 시 에러 메시지 반환
            return {
                "messages": [
                    AIMessage(
                        content="오류: 검증 단계 질문을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."
                    )
                ]
            }

        first_question = questions[0].get("text", "첫 번째 질문을 불러오지 못했습니다.")
        total_q = len(questions)

        print(
            f"[Validation Debug] 질문 생성 완료: total_questions={len(questions)}. "
            "State에 validation_questions 저장 후 첫 질문 반환."
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
            "validation_questions": questions,
            "validation_current_index": 0,
            "validation_answers": [],
        }

    # 2) 질문 리스트는 이미 있고, 사용자 답변(1~5)을 받아 다음 질문으로 진행

    # 2-1) 개발자용 치트키: "개발자 상" / "개발자 하"
    total_q = len(validation_questions)
    key = user_input.strip().replace(" ", "")
    if total_q > 0 and key:
        if key == "개발자상":
            answers = [5] * total_q
            current_index = total_q
        elif key == "개발자하":
            answers = [1] * total_q
            current_index = total_q

        if key in ("개발자상", "개발자하"):
            # 치트키가 적용된 경우, 바로 평가 단계로 진행
            pass
        else:
            # 치트키가 아니면 아래 일반 흐름으로 진행
            total_q = len(validation_questions)  # keep for later

    # 2-2) 일반 흐름: 질문별로 1~5 답변을 하나씩 받기
    if current_index < total_q and key not in ("개발자상", "개발자하"):
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
            # 올바른 입력이 아니면 안내 메시지
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
            f"[Validation Debug] 응답 수신: answer={answer_value}, "
            f"next_index={current_index}/{total_q}"
        )

        # 아직 남은 질문이 있다면 → 다음 질문을 동일 포맷으로 직접 출력 (LLM 재호출 없음)
        if current_index < total_q:
            next_q = validation_questions[current_index]
            next_text = next_q.get("text", "다음 질문을 불러오지 못했습니다.")
            print(
                f"[Validation Debug] 다음 질문 진행: index={current_index}, "
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
                "validation_questions": validation_questions,
                "validation_current_index": current_index,
                "validation_answers": answers,
            }

    # 3) 모든 질문에 답변이 완료된 경우 → 별도 프롬프트로 LLM 호출하여 확률 계산/분기 처리
    print(
        "[Validation Debug] 모든 질문에 대한 응답 완료 → "
        "평가용 LLM 호출 (Validation Result 계산)"
    )
    eval_prompt = """
당신은 임상 심리사입니다. 아래 의심 질환 및 각 질환의 진단 기준,
그리고 각 질문에 대한 사용자의 1~5점 응답을 기반으로
각 질환의 부합 확률을 계산하고, 최종으로 가장 가능성이 높은 질환을 선택하세요.

- 1은 거의 해당되지 않음, 5는 매우 자주/강하게 해당됨을 의미합니다.
- 질문의 target_diagnosis, related_criteria를 참고하여, 각 질환의 점수를 계산하세요.
- 점수는 0.0~1.0 범위의 확률로 환산해 주세요.

출력 시, 사용자에게 보여줄 요약 설명은 자유롭게 작성하되,
아래 INTERNAL_DATA 포맷을 반드시 포함해야 합니다.

---INTERNAL_DATA---
Validated String: [질환명 or None]
Validation JSON: {{"질환A": 0.7, "질환B": 0.4, ...}}
"""

    eval_context = f"""
{eval_prompt}

## 의심 질환 및 기준 (Hypothesis Criteria)
{json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)}

## 질문 리스트 (Validation Questions)
{json.dumps(validation_questions, ensure_ascii=False, indent=2)}

## 사용자 응답 (1~5 Likert, 질문 순서대로)
{json.dumps(answers, ensure_ascii=False, indent=2)}
"""

    eval_response = ask_openai(
        user_input="위 데이터를 바탕으로 Validation 결과를 계산하고 정리해 주세요.",
        context=eval_context,
        conversation_history=None,
    )
    
    user_message = eval_response
    internal_data = ""
    new_state: Dict[str, Any] = {
        "validation_questions": validation_questions,
        "validation_current_index": current_index,
        "validation_answers": answers,
    }
    
    if "---INTERNAL_DATA---" in eval_response:
        parts = eval_response.split("---INTERNAL_DATA---", 1)
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
        
    # Validation JSON 파싱 및 분기 결정
    if "Validation JSON:" in internal_data:
        try:
            json_str = internal_data.split("Validation JSON:", 1)[1].strip()
            probabilities = json.loads(json_str)
            new_state["validation_probabilities"] = probabilities
            
            max_prob = 0.0
            for prob in probabilities.values():
                try:
                    if prob > max_prob:
                        max_prob = prob
                except Exception:
                    continue
            
            # 0.5 이하면 재탐색 (Re-Intake)
            if max_prob <= 0.5:
                new_state["is_re_intake"] = True
                new_state["severity_diagnosis"] = None
            else:
                new_state["is_re_intake"] = False
                
        except Exception as e:
            print(f"Validation JSON 파싱 오류: {e}")
            
    if "Validated String:" in internal_data:
        # Validated String 뒤에 Validation JSON 등이 이어져 있을 수 있으므로,
        # 먼저 해당 구간만 잘라낸 뒤 공백/괄호 등을 정리해서 질환명만 추출한다.
        segment = internal_data.split("Validated String:", 1)[1]
        # Validation JSON 이전까지만 사용
        if "Validation JSON:" in segment:
            segment = segment.split("Validation JSON:", 1)[0]
        diagnosis = segment.strip()
        # 양쪽 대괄호/따옴표 등 불필요한 감싸는 문자 제거
        diagnosis = diagnosis.strip("[]\"' ")
        if diagnosis.lower() != "none" and not new_state.get("is_re_intake", False):
            new_state["severity_diagnosis"] = diagnosis
        
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state,
    }

