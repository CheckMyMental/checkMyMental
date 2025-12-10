# Context 파일 관리 모듈
# 텍스트 파일이나 마크다운 파일에서 context를 읽어오는 기능

import os
from pathlib import Path
import json

# 프로젝트 루트 디렉토리 (frontend 폴더의 상위 디렉토리)
PROJECT_ROOT = Path(__file__).parent.parent

# Context 파일들이 저장될 디렉토리
CONTEXT_DIR = PROJECT_ROOT / "contexts"

# Prompts 파일들이 저장될 디렉토리
PROMPTS_DIR = PROJECT_ROOT / "prompts"


def get_project_root() -> Path:
    """프로젝트 루트 경로를 반환합니다."""
    return PROJECT_ROOT


# 지정된 이름의 파일(.txt나 .md, .json)에서 context를 읽어서 문자열로 반환
def load_context_from_file(filename: str) -> str:
    """
    Context 파일을 읽어서 문자열로 반환합니다.
    
    Args:
        filename: contexts 폴더 기준 상대 경로 (예: "stage_specific/context_stage1_intake.json")
    
    Returns:
        파일 내용 (문자열), 파일이 없으면 빈 문자열
    """
    file_path = CONTEXT_DIR / filename
    
    if not file_path.exists():
        return ""
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return content
    except Exception as e:
        return ""



#문자열을 파일로 저장하는 함수(자동으로 contexts 폴더 생성함)
def save_context_to_file(filename: str, content: str) -> bool:
    CONTEXT_DIR.mkdir(exist_ok=True) 
    
    file_path = CONTEXT_DIR / filename
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        return False

#지정된 이름의 파일(.txt나 .md)에서 context를 읽어서 문자열로 반환
def get_context(context_name: str = None) -> str:
    if context_name is None:
        context_name = "default_context.md"
    context = load_context_from_file(context_name)
    return context


def load_prompt_from_file(filename: str) -> str:
    """
    Prompt 파일을 읽어서 문자열로 반환합니다.
    
    Args:
        filename: prompts 폴더 기준 상대 경로 (예: "stage1_intake.md")
    
    Returns:
        파일 내용 (문자열), 파일이 없으면 빈 문자열
    """
    file_path = PROMPTS_DIR / filename
    
    if not file_path.exists():
        return ""
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return content
    except Exception as e:
        return ""


# 사용 가능한 context 파일 목록을 반환하는 함수
def list_context_files() -> list:
    if not CONTEXT_DIR.exists():
        return []
    
    files = []
    for file_path in CONTEXT_DIR.rglob("*"):  # 재귀적으로 검색
        if file_path.is_file() and file_path.suffix in [".txt", ".md", ".json"]:
            relative_path = file_path.relative_to(CONTEXT_DIR)
            files.append(str(relative_path))
    
    return sorted(files)

