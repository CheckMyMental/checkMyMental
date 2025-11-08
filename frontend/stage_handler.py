# 단계별 상담 프로세스 관리 핸들러
import json
import streamlit as st
from pathlib import Path
from typing import Dict, Optional, Tuple


class StageHandler:
    """4단계 상담 프로세스를 관리하는 핸들러"""
    
    STAGES = {
        1: {
            "name": "intake",
            "prompt_file": "stage1_intake.md",
            "context_files": [
                "stage_specific/context_stage1_intake.json",
                "common/diagnostic_guidelines.json"
            ]
        },
        2: {
            "name": "hypothesis_generation", 
            "prompt_file": "stage2_hypothesis_generation.md",
            "context_files": [
                "stage_specific/context_stage2_hypothesis_generation.json"
            ]
        },
        3: {
            "name": "validation",
            "prompt_file": "stage3_validation.md",
            "context_files": [
                "stage_specific/context_stage3_validation.json"
            ]
        },
        4: {
            "name": "solution_summary",
            "prompt_file": "stage4_solution_summary.md",
            "context_files": [
                "stage_specific/context_stage4_solution_summary.json"
            ]
        }
    }
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.prompts_dir = self.base_path / "prompts"
        self.contexts_dir = self.base_path / "contexts"
        
        # session_state에 현재 단계 초기화
        if "current_stage" not in st.session_state:
            st.session_state.current_stage = 1
        if "stage_data" not in st.session_state:
            st.session_state.stage_data = {}
        # Stage 1 대화 턴 수 추적 (질문-응답 쌍)
        if "stage1_turn_count" not in st.session_state:
            st.session_state.stage1_turn_count = 0
    
    def get_current_stage(self) -> int:
        """현재 단계 반환"""
        return st.session_state.current_stage
    
    def get_stage_name(self, stage: Optional[int] = None) -> str:
        """단계 이름 반환"""
        if stage is None:
            stage = self.get_current_stage()
        return self.STAGES.get(stage, {}).get("name", "unknown")
    
    def load_prompt(self, stage: int) -> str:
        """특정 단계의 프롬프트를 로드"""
        if stage not in self.STAGES:
            raise ValueError(f"Invalid stage: {stage}")
        
        prompt_file = self.prompts_dir / self.STAGES[stage]["prompt_file"]
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt_content = f.read()
                print(f"\n{'='*80}")
                print(f"[Stage {stage}] 프롬프트 파일 로드: {self.STAGES[stage]['prompt_file']}")
                print(f"{'='*80}")
                print(f"프롬프트 내용 (처음 500자):\n{prompt_content[:500]}...")
                print(f"{'='*80}\n")
                return prompt_content
        except Exception as e:
            print(f"프롬프트 로드 오류 (Stage {stage}): {e}")
            return ""
    
    def load_context(self, stage: int) -> Dict:
        """특정 단계의 context JSON 파일들을 모두 로드하여 통합"""
        if stage not in self.STAGES:
            raise ValueError(f"Invalid stage: {stage}")
        
        context_files = self.STAGES[stage].get("context_files", [])
        merged_context = {}
        
        for context_file_path in context_files:
            context_file = self.contexts_dir / context_file_path
            
            try:
                if context_file.exists():
                    with open(context_file, "r", encoding="utf-8") as f:
                        context_data = json.load(f)
                        # 파일명을 키로 사용하여 통합 (중복 방지)
                        file_key = context_file_path.replace("/", "_").replace(".json", "")
                        merged_context[file_key] = context_data
                else:
                    print(f"[경고] Context 파일을 찾을 수 없습니다: {context_file_path}")
            except Exception as e:
                print(f"Context 로드 오류 (Stage {stage}, 파일: {context_file_path}): {e}")
        
        return merged_context
    
    def get_stage_materials(self, stage: Optional[int] = None) -> Tuple[str, Dict]:
        """특정 단계(또는 현재 단계)의 prompt와 context를 함께 반환"""
        if stage is None:
            stage = self.get_current_stage()
        
        prompt = self.load_prompt(stage)
        context = self.load_context(stage)
        
        return prompt, context
    
    def move_to_next_stage(self) -> bool:
        """다음 단계로 이동 (성공 여부 반환)"""
        current = st.session_state.current_stage
        
        if current < 4:
            st.session_state.current_stage = current + 1
            print(f"Stage {current} → Stage {current + 1} 이동")
            return True
        else:
            print("이미 마지막 단계입니다.")
            return False
    
    def move_to_stage(self, stage: int) -> bool:
        """특정 단계로 직접 이동"""
        if stage in self.STAGES:
            st.session_state.current_stage = stage
            print(f"Stage {stage}로 이동")
            return True
        return False
    
    def reset_stage(self):
        """단계를 처음으로 리셋"""
        st.session_state.current_stage = 1
        st.session_state.stage_data = {}
        st.session_state.stage1_turn_count = 0
    
    def increment_stage1_turn(self):
        """Stage 1의 대화 턴 수 증가"""
        if st.session_state.current_stage == 1:
            st.session_state.stage1_turn_count += 1
    
    def get_stage1_turn_count(self) -> int:
        """Stage 1의 현재 대화 턴 수 반환"""
        return st.session_state.get("stage1_turn_count", 0)
    
    def save_stage_output(self, stage: int, data: Dict):
        """특정 단계의 출력 데이터를 저장 (다음 단계 입력으로 활용)"""
        st.session_state.stage_data[f"stage_{stage}"] = data
    
    def get_stage_output(self, stage: int) -> Optional[Dict]:
        """이전 단계의 출력 데이터 가져오기"""
        return st.session_state.stage_data.get(f"stage_{stage}")
    
    def should_transition(self, response: str, conversation_history: list = None) -> bool:
        """
        AI 응답을 분석해서 다음 단계로 넘어갈지 판단
        - Stage 1: Summary String이 생성되고, 최소 3턴 이상의 대화가 진행되었을 때만 다음 단계로
        - Stage 2: Hypothesis String이 생성되면 다음 단계로 (내부 처리 단계)
        - Stage 3: Validated String이 생성되면 다음 단계로
        
        Args:
            response: AI 응답 텍스트
            conversation_history: 대화 히스토리 (선택적, Stage 1 검증용)
        """
        current = self.get_current_stage()
        
        # Stage 1: Summary String이 생성되고, 충분한 정보가 수집되었을 때만 다음 단계로
        if current == 1:
            if "Summary String:" in response:
                # 최소 턴 수 확인 (질문-응답 쌍)
                turn_count = self.get_stage1_turn_count()
                
                # 대화 히스토리에서도 확인 (추가 검증)
                if conversation_history:
                    # Stage 1에서의 사용자 메시지 수 확인 (질문에 대한 응답)
                    stage1_user_messages = [
                        msg for msg in conversation_history 
                        if msg.get("role") == "user"
                    ]
                    user_message_count = len(stage1_user_messages)
                else:
                    user_message_count = turn_count
                
                # 최소 3턴 이상의 대화가 진행되었는지 확인
                if turn_count >= 3 or user_message_count >= 3:
                    print(f"[Stage 1] 충분한 정보 수집 완료 (턴 수: {turn_count}, 사용자 메시지: {user_message_count})")
                    # 요약 리포트 저장은 chat_handler에서 처리
                    return True
                else:
                    print(f"[Stage 1] 정보 수집 부족 - 전환 거부 (턴 수: {turn_count}, 사용자 메시지: {user_message_count}, 최소 필요: 3턴)")
                    return False
        
        # Stage 2: Hypothesis String이 생성되면 다음 단계로 (내부 처리 단계)
        if current == 2:
            if "Hypothesis String:" in response:
                # 가설 리포트 저장은 chat_handler에서 처리
                return True
        
        # Stage 3: Validated String이 생성되면 다음 단계로
        if current == 3:
            if "Validated String:" in response:
                # 확정 질환명 저장은 chat_handler에서 처리
                return True
        
        return False

