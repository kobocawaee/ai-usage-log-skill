"""找出本專案的 Claude Code 對話紀錄（SPEC 3.1、2）。

用法：
    python find_sessions.py [--project <專案路徑>] [--claude-dir <~/.claude/projects>]
                            [--state <ai-log/.ai-usage-log-state.json>] [--tz Asia/Taipei] [--json]

不依賴「專案路徑編碼成資料夾名稱」的規則：逐一讀取每個 .jsonl 第一筆有 cwd 欄位的紀錄，
比對是否等於專案路徑（不分大小寫、斜線方向、結尾斜線；也接受 cwd 在專案資料夾之下）。
只列出頂層的 .jsonl（不含 subagents）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_session import _text_blocks, clean_text  # noqa: E402


def norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(str(p))).replace("\\", "/").rstrip("/")


def default_claude_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "projects"


SNIPPET_LEN = 30


def snippet(text: str, limit: int = SNIPPET_LEN) -> str:
    """把第一句人工輸入壓成一行短摘要（沒有標題的對話用它辨認）。"""
    one = " ".join(clean_text(text).split())
    return one if len(one) <= limit else one[:limit].rstrip() + "…"


def scan_file(path: Path) -> dict | None:
    """單趟掃描：cwd、起訖時間、人工輸入次數、第一句人工輸入。檔案不是 UTF-8 JSONL 時回傳 None。"""
    cwd = first = last = title = first_input = None
    humans = 0
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if '"cwd"' not in line and '"timestamp"' not in line and '"ai-title"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if o.get("type") == "ai-title" and o.get("aiTitle"):
                    title = o["aiTitle"]  # 與 VS Code 對話清單顯示的標題相同；取最後一筆
                if cwd is None and o.get("cwd"):
                    cwd = o["cwd"]
                if o.get("type") in ("user", "assistant") and not o.get("isSidechain") and o.get("timestamp"):
                    first = first or o["timestamp"]
                    last = o["timestamp"]
                    if o["type"] == "user" and (o.get("origin") or {}).get("kind") == "human":
                        humans += 1
                        if first_input is None:
                            raw = "\n".join(_text_blocks((o.get("message") or {}).get("content")))
                            first_input = snippet(raw) or None
    except (OSError, UnicodeDecodeError):
        return None
    return {"cwd": cwd, "first": first, "last": last, "humans": humans, "title": title,
            "first_input": first_input}


def _local(ts: str | None, tz: ZoneInfo) -> str:
    if not ts:
        return ""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d %H:%M")


def find_sessions(project: str, claude_dir: Path, state_path: Path | None, tz_name: str = "Asia/Taipei") -> list[dict]:
    tz = ZoneInfo(tz_name)
    processed = {}
    if state_path and Path(state_path).is_file():
        processed = json.loads(Path(state_path).read_text(encoding="utf-8")).get("sessions", {})
    target = norm(project)
    out = []
    if not Path(claude_dir).is_dir():
        return out
    for proj_dir in Path(claude_dir).iterdir():
        if not proj_dir.is_dir():
            continue
        for jl in proj_dir.glob("*.jsonl"):
            info = scan_file(jl)
            if not info or not info["cwd"]:
                continue
            c = norm(info["cwd"])
            if c != target and not c.startswith(target + "/"):
                continue
            sid = jl.stem
            out.append({
                "session_id": sid,
                "title": info["title"] or (f"（無標題）{info['first_input']}" if info["first_input"] else "（無標題）"),
                "first_input": info["first_input"] or "",
                "path": str(jl),
                "start": _local(info["first"], tz),
                "end": _local(info["last"], tz),
                "human_inputs": info["humans"],
                "size_kb": round(jl.stat().st_size / 1024),
                "has_subagents": (proj_dir / sid / "subagents").is_dir(),
                "processed": sid in processed,
                "_sort": info["first"] or "",
            })
    out.sort(key=lambda s: s["_sort"], reverse=True)
    for s in out:
        del s["_sort"]
    return out


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--claude-dir", type=Path, default=default_claude_dir())
    ap.add_argument("--state", type=Path)
    ap.add_argument("--tz", default="Asia/Taipei")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="連已處理過的也列出（預設只列未處理）")
    a = ap.parse_args(argv)
    state = a.state or Path(a.project) / "ai-log" / ".ai-usage-log-state.json"
    rows = find_sessions(a.project, a.claude_dir, state, a.tz)
    if not a.all:
        rows = [r for r in rows if not r["processed"]]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("找不到尚未處理的對話紀錄。（可加 --all 列出全部，或直接提供 .jsonl 路徑）")
        return 0
    print("| # | 標題 | 開始 | 結束 | 人工輸入 | session | 狀態 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(rows, 1):
        print(f"| {i} | {r['title']} | {r['start']} | {r['end']} | {r['human_inputs']} | "
              f"{r['session_id'][:8]} | {'已處理' if r['processed'] else '未處理'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
