import json
import re  # 모듈을 맨 위에서 import 하는 것이 정석입니다.
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from graph.state import CounselingState
from frontend.openai_api import ask_gemini
from frontend.context_handler import load_context_from_file, load_prompt_from_file

def validation_node(state: CounselingState) -> Dict[str, Any]:
    """
    Validation Stage (3단계) 처리 노드
    - 의심 질환 검증을 위한 5지선다 질문 생성 및 응답 수집
    - 1턴: 질문 생성 (질환 기준 기반)
    - 2턴~: 사용자 응답 수집 및 진행
    - 마지막: 모든 답변 수집 후 확률 계산 및 결과 도출
    """
    
    print("=" * 60)
    print("[Stage 3: Validation] 노드 실행 시작")
    print("=" * 60)
    
    messages = state['messages']
    last_message = messages[-1] if messages else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 상태 정보 가져오기
    hypothesis_criteria = state.get("hypothesis_criteria", [])
    if not hypothesis_criteria:
         return {"messages": [AIMessage(content="오류: 가설 검증을 위한 기준 데이터가 없습니다. 상담을 초기화해주세요.")]}
    
    # 이미 확률이 계산되었으면 더 이상 질문하지 않고 빈 상태 반환 (edges.py에서 자동 분기)
    existing_probabilities = state.get("validation_probabilities")
    if existing_probabilities:
        print("[Validation Node] ⚠️ 이미 확률 계산 완료됨 - 더 이상 질문 생성하지 않음, edges.py에서 자동 분기")
        # 빈 상태 반환하여 edges.py에서 자동으로 다음 단계로 분기하도록 함
        return {}

    # 프롬프트 로드 (매번 새로 로드하여 최신 상태 유지)
    print(f"[Validation Node] 프롬프트 및 컨텍스트 파일 로드 시작...")
    base_prompt = load_prompt_from_file("stage3_validation.md")
    if not base_prompt:
        base_prompt = "기본 프롬프트 로드 실패: 파일을 찾을 수 없습니다."
        print(f"[Validation Node] ⚠ 프롬프트 파일 로드 실패: stage3_validation.md")
    else:
        print(f"[Validation Node] ✓ 프롬프트 로드 완료: stage3_validation.md ({len(base_prompt)} 문자)")

    # Context 로드 (매번 새로 로드)
    validation_context = load_context_from_file("stage_specific/context_stage3_validation.json")
    if validation_context:
        print(f"[Validation Node] ✓ 컨텍스트 로드 완료: context_stage3_validation.json ({len(validation_context)} 문자)")
    else:
        print(f"[Validation Node] ⚠ 컨텍스트 로드 실패: context_stage3_validation.json")
    
    # JSON 데이터 문자열 준비
    criteria_json_str = json.dumps(hypothesis_criteria, ensure_ascii=False, indent=2)
    
    # 히스토리 처리 및 진행 상태 추적
    history = []
    found_validation_start = False
    validation_messages = []
    
    # Validation 단계 메시지 추출 (Hypothesis 이후)
    for msg in messages[:-1]:  # 현재 메시지 제외
        if isinstance(msg, AIMessage):
            # Hypothesis 단계의 결과 메시지 확인
            if "의심 질환" in msg.content or "질환 후보" in msg.content:
                found_validation_start = True
                continue
            # Validation 시작 이후 메시지만 수집
            if found_validation_start:
                validation_messages.append(msg)
        elif isinstance(msg, HumanMessage):
            if found_validation_start:
                validation_messages.append(msg)
    
    # Validation 메시지가 없으면 최근 몇 개만 사용
    if not validation_messages:
        recent_messages = messages[-6:-1] if len(messages) > 1 else []
        validation_messages = recent_messages
    
    # 히스토리 변환 (최근 10개로 제한)
    history = [
        {"role": "user" if isinstance(m, HumanMessage) else "model", "content": m.content}
        for m in validation_messages[-10:]
    ]
    
    # 이미 질문한 질병 추적 (히스토리에서 분석)
    questioned_diseases = []
    
    # hypothesis_criteria에서 질병 목록 추출
    disease_list = []
    for criteria in hypothesis_criteria:
        # "[질환명] 기준내용" 형식에서 질환명 추출
        if isinstance(criteria, str) and criteria.startswith("["):
            match = re.match(r'\[([^\]]+)\]', criteria)
            if match:
                disease_name = match.group(1)
                if disease_name not in disease_list:
                    disease_list.append(disease_name)
    
    # 히스토리에서 이미 질문한 질병 확인
    # 사용자 응답을 확인하여 질문이 완료되었는지 판단
    user_responses_count = 0
    qa_pairs_by_disease = {disease: 0 for disease in disease_list}  # 질병별 질문-답변 쌍 수
    
    # 질문-답변 쌍 추적 (더 정확한 완료 감지)
    previous_ai_message = None
    for i, msg in enumerate(validation_messages):
        if isinstance(msg, AIMessage):
            content = msg.content.lower()
            previous_ai_message = msg
            
            # 질문 메시지에 질병명이 포함되어 있는지 확인
            for disease in disease_list:
                disease_lower = disease.lower()
                # 질병명이 포함되어 있고, 질문 관련 키워드가 있으면 질문한 것으로 간주
                if disease_lower in content and ("질문" in content or "question" in content or "선택" in content or "1~5" in content or "1-5" in content):
                    if disease not in questioned_diseases:
                        questioned_diseases.append(disease)
                        print(f"[Validation Node] 질병 '{disease}' 질문 감지됨")
        elif isinstance(msg, HumanMessage):
            # 사용자 응답이 있으면 (숫자나 답변 패턴) 질문에 답변한 것으로 간주
            user_content = msg.content.strip()
            
            # 숫자 답변 (1-5) 또는 짧은 텍스트 답변으로 판단
            is_valid_response = False
            if user_content:
                # 숫자 답변 (1-5)
                if user_content.isdigit():
                    num = int(user_content)
                    if 1 <= num <= 5:
                        is_valid_response = True
                # 여러 숫자 답변 (예: "1, 2, 3")
                elif re.match(r'^[\d\s,]+$', user_content):
                    is_valid_response = True
                # 짧은 텍스트 답변
                elif len(user_content) < 50:
                    is_valid_response = True
            
            if is_valid_response:
                user_responses_count += 1
                # 이전 AI 메시지에서 질병명 찾기
                if previous_ai_message:
                    prev_content = previous_ai_message.content.lower()
                    for disease in disease_list:
                        if disease.lower() in prev_content:
                            qa_pairs_by_disease[disease] = qa_pairs_by_disease.get(disease, 0) + 1
                            print(f"[Validation Node] 질병 '{disease}'에 대한 답변 감지 (총 {qa_pairs_by_disease[disease]}회)")
    
    # 남은 질병 목록
    remaining_diseases = [d for d in disease_list if d not in questioned_diseases]
    
    # 진행 상태 문자열 준비
    questioned_diseases_str = ", ".join(questioned_diseases) if questioned_diseases else "없음"
    next_disease_str = remaining_diseases[0] if remaining_diseases else "없음 (모든 질문 완료 - 반드시 확률 계산 필요!)"
    all_questioned_str = "예" if len(questioned_diseases) >= len(disease_list) else "아니오"
    
    # 모든 질문이 완료되었는지 확인 (더 정확한 판단)
    # 조건 1: 모든 질병에 대해 질문이 나왔는지
    # 조건 2: 충분한 질문-답변 쌍이 있는지 (3개 질병 * 최소 1회 이상 = 최소 3회 이상)
    all_diseases_questioned = len(questioned_diseases) >= len(disease_list) and len(disease_list) > 0
    sufficient_responses = user_responses_count >= len(disease_list)  # 최소 질병 수만큼 답변
    
    all_questions_complete = all_diseases_questioned and sufficient_responses
    
    print(f"[Validation Node] 히스토리 메시지 수: {len(history)}개 (전체: {len(messages)}개)")
    print(f"[Validation Node] 질문 진행 상태:")
    print(f"  - 전체 질병 목록: {disease_list}")
    print(f"  - 이미 질문한 질병: {questioned_diseases}")
    print(f"  - 남은 질병: {remaining_diseases}")
    print(f"  - 질문-답변 쌍: {qa_pairs_by_disease}")
    print(f"  - 사용자 응답 총 개수: {user_responses_count}")
    print(f"  - 모든 질병 질문 완료: {all_diseases_questioned}")
    print(f"  - 충분한 응답 수집: {sufficient_responses}")
    print(f"  - 모든 질문 완료 여부: {all_questions_complete}")
    
    # 모든 질문이 완료되었으면 강제로 확률 계산 단계로 이동
    if all_questions_complete:
        print("[Validation Node] ⚠️ 모든 질문 완료! 확률 계산 단계로 강제 이동")

    validation_json_example = '{"질환A": 0.7, "질환B": 0.4}'

    # 시스템 지시사항 구성
    system_instructions = (
        base_prompt
        + "\n\n## 현재 상담 진행 상황\n- **의심 질환 및 기준**:\n"
        + criteria_json_str
        + """

## Validation 단계 처리 지침

### 현재 질문 진행 상태:
- **전체 질병 목록**: """
        + ", ".join(disease_list)
        + """
- **이미 질문한 질병**: """
        + questioned_diseases_str
        + """
- **다음에 질문할 질병**: """
        + next_disease_str
        + """
- **모든 질병에 대한 질문 완료 여부**: """
        + all_questioned_str
        + """

### 질문 진행 방식 (매우 중요!):
"""
    + ("⚠️⚠️⚠️ 모든 질병에 대한 질문이 완료되었습니다! 더 이상 질문하지 마시고 반드시 확률을 계산하세요! ⚠️⚠️⚠️\n\n" if all_questions_complete else "")
    + """1. **한 번에 하나의 질병만 질문하세요!** - 이미 질문한 질병은 다시 질문하지 마세요!
   - 다음에 질문할 질병("""
        + next_disease_str
        + """)만 질문하세요!
   
2. **같은 질환에 대한 질문들을 묶어서 한 번에 제시**:
   - 예: "[다음 질병명]에 대한 질문들입니다. 각 질문에 대해 1~5 중 하나를 선택해주세요:\n\n1) 질문1?\n2) 질문2?\n3) 질문3?..."
   - 한 질병의 모든 질문을 한 번에 제시하고, 사용자가 그 질병에 대한 답변을 모두 받은 후에만 다음 질병으로 진행하세요.
   
3. **절대로 여러 질병의 질문을 한 번에 제시하지 마세요!**
   - 질병1 질문 → (답변 완료 대기) → 질병2 질문 → (답변 완료 대기) → 질병3 질문

4. **모든 질병에 대한 질문이 완료되면 (매우 중요!)**:
   - ⚠️⚠️⚠️ 절대로 더 이상 질문을 생성하지 마세요! ⚠️⚠️⚠️
   - 확률이 이미 계산되었다면 더 이상 질문하지 마세요!
   - 반드시 모든 질환에 대한 확률을 계산하고 결과를 도출하세요!
   - 아래 형식으로 반드시 출력하세요:
   
   ---INTERNAL_DATA---
   Validated String: [최종 확정된 질환명 또는 None]
   Validation JSON: {"질환1": 0.6, "질환2": 0.4, "질환3": 0.3}
   
   - 확률은 0.0~1.0 범위로 설정하세요
   - 세 질환 모두 50% (0.5) 이하이면 Validated String: None으로 설정하세요
   - 그렇지 않으면 확률이 가장 높은 질환명을 Validated String에 설정하세요
   - 확률 계산 후에는 절대로 추가 질문을 하지 마세요!

## 출력 형식 (매우 중요!)
**사용자에게 보여지는 메시지**:
- 자연스러운 대화 형식으로 질문을 제시하세요.
- 예: "다음은 [질환명]에 대한 질문들입니다. 각 질문에 대해 1~5 중 하나를 선택해주세요:\n\n1) 질문 내용 1?\n2) 질문 내용 2?\n..."
- JSON 형식, 질환명 목록, 진단 기준 등은 사용자에게 보여주지 마세요!
- 오직 자연스러운 질문 내용만 사용자에게 전달하세요.

**내부 데이터 (---INTERNAL_DATA--- 섹션에만 포함)**:
- 질문 진행 상태 추적용 정보 (필요한 경우)
- 완료 시에만:
    - `Validated String:` 뒤에 최종 확정된 질환명 (없으면 None)
    - `Validation JSON:` 뒤에 각 질환별 확률 JSON 하나 출력

## 주의사항
- 절대로 JSON 형식, 질환명 목록, 진단 기준 등을 사용자에게 직접 보여주지 마세요!
- 사용자가 보는 메시지는 오직 자연스러운 질문 내용만 포함해야 합니다.
- 모든 내부 데이터는 반드시 `---INTERNAL_DATA---` 구분선 아래에만 작성하세요.

## Internal Data Format
Validated String: [질환명 또는 None]
Validation JSON: """
        + validation_json_example
    )

    # LLM 호출
    full_context = system_instructions + "\n\n## Context Data\n" + validation_context
    
    # 모든 질문이 완료되었다면 강제로 확률 계산 요청 (기존 확률이 없을 때만)
    if all_questions_complete and not existing_probabilities:
        user_input = "⚠️⚠️⚠️ 모든 질병에 대한 질문이 완료되었습니다. 절대로 더 이상 질문하지 마세요! 지금 바로 모든 질환에 대한 확률을 계산하고 결과를 도출해주세요. 반드시 ---INTERNAL_DATA--- 섹션에 Validated String과 Validation JSON을 포함하세요. 더 이상 어떤 질문도 생성하지 마세요!"
        print("[Validation Node] ⚠️ 모든 질문 완료됨 - 확률 계산 강제 요청 (질문 금지)")
    
    response_text = ask_gemini(
        user_input=user_input if user_input else "Validation 단계를 시작합니다. 질문을 생성해주세요.",
        context=full_context,
        conversation_history=history
    )
    
    # 응답 파싱
    user_message = response_text
    internal_data = ""
    new_state = {}
    
    if "---INTERNAL_DATA---" in response_text:
        parts = response_text.split("---INTERNAL_DATA---")
        user_message = parts[0].strip()
        internal_data = parts[1].strip()
    
    # 사용자 메시지에서 JSON 형식 및 불필요한 패턴 제거
    # JSON 코드 블록 제거
    json_code_block = r'```json\s*\{[\s\S]*?\}\s*```'
    user_message = re.sub(json_code_block, '', user_message, flags=re.IGNORECASE)
    
    # 단순 JSON 객체 패턴 제거
    json_object_patterns = [
        r'\{[^{}]*"(?:questions|diagnoses|질환|질병|question|diagnosis|target_diagnosis|related_criteria)"[^{}]*\}',
        r'\{"[^"]*":\s*\[[^\]]+\]\}',
        r'\{[^{}]*"id"[^{}]*"text"[^{}]*\}',
    ]
    for pattern in json_object_patterns:
        user_message = re.sub(pattern, '', user_message, flags=re.DOTALL | re.IGNORECASE)
    
    # 질환명이나 라벨과 함께 나오는 JSON 형식 제거
    json_with_label = r'(질환|질병|diagnosis|disease|questions|질문):\s*\{[^}]+\}'
    user_message = re.sub(json_with_label, '', user_message, flags=re.IGNORECASE)
    
    # 배열 형태의 JSON 제거
    json_array = r'\[[^\[\]]*\{[^}]+\}[^\[\]]*\]'
    user_message = re.sub(json_array, '', user_message, flags=re.DOTALL)
    
    # 여러 줄에 걸친 JSON 블록 제거
    multiline_json = r'\{\s*"[^"]*":\s*\[[^\]]+\][^}]*\}'
    user_message = re.sub(multiline_json, '', user_message, flags=re.DOTALL)
    
    # 정리: 여러 공백을 하나로, 빈 줄 제거
    user_message = re.sub(r'\n\s*\n\s*\n+', '\n\n', user_message)
    user_message = user_message.strip()
    
    # JSON만 남았거나 메시지가 너무 짧은 경우 검증
    if len(user_message) < 20 or re.search(r'^[\s\{\[\}\]]+$', user_message):
        print("[Validation Node] ⚠ 사용자 메시지에서 JSON만 발견되어 제거됨, 기본 메시지 사용")
        # 이전 응답에서 자연스러운 부분 찾기
        if "---INTERNAL_DATA---" in response_text:
            original = response_text.split("---INTERNAL_DATA---")[0].strip()
            # 한글 문장이 5글자 이상 있으면 복구 시도
            if re.search(r'[가-힣]{5,}', original):
                user_message = re.sub(json_code_block, '', original, flags=re.IGNORECASE)
                user_message = re.sub(r'\{[^{}]*"', '', user_message)
                user_message = user_message.strip()
        
        if len(user_message) < 20:
            user_message = "검증을 위한 질문을 진행하겠습니다."
        
    # 결과 분석 (확률 및 재탐색 여부)
    if "Validation JSON:" in internal_data:
        try:
            json_str = internal_data.split("Validation JSON:")[1].strip()
            probabilities = json.loads(json_str)
            new_state["validation_probabilities"] = probabilities
            
            print(f"[Validation Node] ✓ 확률 계산 완료: {probabilities}")
            
            # 확률 체크
            max_prob = 0.0
            for prob in probabilities.values():
                if prob > max_prob:
                    max_prob = prob
            
            # 0.5 이하면 재탐색 (Re-Intake)
            if max_prob <= 0.5:
                new_state["is_re_intake"] = True
                new_state["severity_diagnosis"] = None # 진단 유보
                print(f"[Validation Node] → Re-Intake 결정 (최대 확률: {max_prob} <= 0.5)")
                print(f"[Validation Node] ✓ 상태 설정 완료: is_re_intake=True, severity_diagnosis=None")
            else:
                new_state["is_re_intake"] = False
                # 확률이 가장 높은 질환을 severity_diagnosis로 자동 설정
                top_diagnosis = max(probabilities.items(), key=lambda x: x[1])[0]
                new_state["severity_diagnosis"] = top_diagnosis
                print(f"[Validation Node] → Severity 단계로 진행 (최대 확률: {max_prob}, Top 질환: {top_diagnosis})")
                print(f"[Validation Node] ✓ 상태 설정 완료: is_re_intake=False, severity_diagnosis={top_diagnosis}")
                
        except Exception as e:
            print(f"[Validation Node] ✗ Validation JSON 파싱 오류: {e}")
            
    if "Validated String:" in internal_data:
        diagnosis = internal_data.split("Validated String:")[1].strip()
        # "None"이 아니고 재탐색 모드가 아니면 진단명 설정
        if diagnosis.lower() != "none" and not new_state.get("is_re_intake", False):
             new_state["severity_diagnosis"] = diagnosis
             print(f"[Validation Node] ✓ 확정 진단명: {diagnosis}")
    
    # ⚠️ 중요: 모든 질문이 완료되었는데도 LLM이 확률을 계산하지 않은 경우 강제 처리
    if all_questions_complete and not new_state.get("validation_probabilities"):
        print("[Validation Node] ⚠️⚠️⚠️ 모든 질문 완료되었으나 확률 계산되지 않음 - 코드 레벨에서 강제 처리")
        # 모든 질병에 대해 낮은 확률로 설정 (모두 0.3 이하) -> Re-Intake로 자동 분기
        forced_probabilities = {disease: 0.3 for disease in disease_list}
        new_state["validation_probabilities"] = forced_probabilities
        new_state["is_re_intake"] = True
        new_state["severity_diagnosis"] = None
        user_message = "검증이 완료되었습니다. 추가 정보가 필요하여 다시 질문드리겠습니다."
        print(f"[Validation Node] ✓ 강제 확률 설정: {forced_probabilities} -> Re-Intake")
        print(f"[Validation Node] ✓ 상태 설정 완료: is_re_intake=True, severity_diagnosis=None")
    
    # 확률이 계산되었으면 더 이상 질문하지 않도록 사용자 메시지 수정
    if new_state.get("validation_probabilities"):
        if not all_questions_complete:  # 모든 질문 완료 전에 확률이 계산된 경우만 메시지 변경
            user_message = "검증이 완료되었습니다. 결과를 분석하겠습니다."
        print("[Validation Node] ⚠️ 확률 계산 완료 - 더 이상 질문하지 않음")
        print(f"[Validation Node] 최종 상태: is_re_intake={new_state.get('is_re_intake')}, severity_diagnosis={new_state.get('severity_diagnosis')}")
        
    return {
        "messages": [AIMessage(content=user_message)],
        **new_state
    }