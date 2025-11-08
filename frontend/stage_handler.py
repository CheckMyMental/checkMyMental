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
            "context_file": "stage_specific/context_stage1_intake.json"
        },
        2: {
            "name": "hypothesis_generation", 
            "prompt_file": "stage2_hypothesis_generation.md",
            "context_file": "stage_specific/context_stage2_hypothesis_generation.json"
        },
        3: {
            "name": "validation",
            "prompt_file": "stage3_validation.md",
            "context_file": "stage_specific/context_stage3_validation.json"
        },
        4: {
            "name": "solution_summary",
            "prompt_file": "stage4_solution_summary.md",
            "context_file": "stage_specific/context_stage4_solution_summary.json"
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
                return f.read()
        except Exception as e:
            print(f"프롬프트 로드 오류 (Stage {stage}): {e}")
            return ""
    
    def load_context(self, stage: int) -> Dict:
        """특정 단계의 context JSON을 로드"""
        if stage not in self.STAGES:
            raise ValueError(f"Invalid stage: {stage}")
        
        context_file = self.contexts_dir / self.STAGES[stage]["context_file"]
        
        try:
            with open(context_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Context 로드 오류 (Stage {stage}): {e}")
            return {}
    
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
    
    def save_stage_output(self, stage: int, data: Dict):
        """특정 단계의 출력 데이터를 저장 (다음 단계 입력으로 활용)"""
        st.session_state.stage_data[f"stage_{stage}"] = data
    
    def get_stage_output(self, stage: int) -> Optional[Dict]:
        """이전 단계의 출력 데이터 가져오기"""
        return st.session_state.stage_data.get(f"stage_{stage}")
    
    def should_transition(self, response: str) -> bool:
        """
        AI 응답을 분석해서 다음 단계로 넘어갈지 판단
        - Stage 1: 자연어 요약 리포트가 생성되면 다음 단계로
        - Stage 2: 가설 리포트가 생성되면 다음 단계로 (내부 처리 단계)
        - Stage 3: 확정 질환명이 나오면 다음 단계로
        """
        current = self.get_current_stage()
        
        # Stage 1: 자연어 요약 리포트가 생성되면 다음 단계로
        if current == 1:
            if "초기 접수 요약 리포트" in response or "## 초기 접수 요약 리포트" in response:
                # 요약 리포트를 저장
                self.save_stage_output(1, {"summary_report": response})
                return True
        
        # Stage 2: 가설 리포트가 생성되면 다음 단계로 (내부 처리 단계)
        if current == 2:
            if "가설 생성 리포트" in response or "## 가설 생성 리포트" in response:
                # 가설 리포트를 저장
                self.save_stage_output(2, {"hypothesis_report": response})
                return True
        
        # Stage 3: 확정 질환명이 나오면 다음 단계로
        if current == 3:
            if "확정 질환명" in response or "## 진단 검증 결과" in response:
                # 확정 질환명을 저장
                self.save_stage_output(3, {"validation_result": response})
                return True
        
        return False

