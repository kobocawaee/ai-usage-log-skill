"""在專案裡尋找名為 ai-log 的資料夾（用來決定產出位置）。

用法：
    python find_ai_log.py --project <專案根目錄> [--depth 3]

輸出 JSON：{"project": "...", "found": ["ai-log", "sports-center/ai-log"]}
- 路徑都是相對於專案根目錄、用 / 分隔，專案根目錄下的 ai-log 排在最前面，其餘依路徑排序。
- 找不到時 found 是空陣列。
- 只找名稱剛好是 ai-log 的資料夾（不分大小寫）；略過 .git、node_modules、虛擬環境、
  _bmad 等與產出無關的資料夾，找不到太深的（預設最多往下 3 層）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

NAME = "ai-log"
SKIP = {".git", ".claude", "node_modules", "venv", ".venv", "env", "__pycache__",
        "_bmad", "_bmad-output", ".idea", ".vscode", "dist", "build", "storage"}


def find_ai_logs(project: Path, depth: int = 3) -> list[str]:
    root = Path(project).resolve()
    found: list[str] = []
    for cur, dirs, _files in os.walk(root):
        rel = Path(cur).relative_to(root)
        level = 0 if str(rel) == "." else len(rel.parts)
        keep = []
        for d in dirs:
            if d.lower() == NAME:
                found.append((rel / d).as_posix() if level else d)
                continue  # 不再往 ai-log 裡面找
            if d in SKIP or level + 1 >= depth:
                continue
            keep.append(d)
        dirs[:] = keep
    return sorted(found, key=lambda p: (p.count("/"), p.lower()))


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--depth", type=int, default=3)
    a = ap.parse_args(argv)
    print(json.dumps({"project": str(Path(a.project).resolve()), "found": find_ai_logs(Path(a.project), a.depth)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
