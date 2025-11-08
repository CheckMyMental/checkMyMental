# Context 파일 관리 모듈
# 텍스트 파일이나 마크다운 파일에서 context를 읽어오는 기능

import os
from pathlib import Path


# Context 파일들이 저장될 디렉토리 (상위 폴더의 contexts)
CONTEXT_DIR = Path(__file__).parent.parent / "contexts"


# 지정된 이름의 파일(.txt나 .md)에서 context를 읽어서 문자열로 반환
def load_context_from_file(filename: str) -> str:
    # 파일에서 context를 읽어옵니다.
    file_path = CONTEXT_DIR / filename
    
    if not file_path.exists():
        print(f"[Context Handler] 파일을 찾을 수 없습니다: {filename}")
        return ""
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return content
    except Exception as e:
        print(f"[Context Handler] Context 파일 읽기 오류 ({filename}): {e}")
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
        print(f"Context 파일 저장 오류 ({filename}): {e}")
        return False

#지정된 이름의 파일(.txt나 .md)에서 context를 읽어서 문자열로 반환
def get_context(context_name: str = None) -> str:
    if context_name is None:
        context_name = "default_context.md"
    context = load_context_from_file(context_name)
    return context


# 사용 가능한 context 파일 목록을 반환하는 함수
def list_context_files() -> list:
    if not CONTEXT_DIR.exists():
        return []
    
    files = []
    for file_path in CONTEXT_DIR.iterdir():
        if file_path.is_file() and file_path.suffix in [".txt", ".md"]:
            files.append(file_path.name)
    
    return sorted(files)

