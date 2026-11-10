"""把「個人檔案」加進專案的 .gitignore（可重複執行，不會重複寫入，也不會動到既有內容）。

用法：
    python ensure_gitignore.py --project <專案根目錄> [--output-dir ai-log]

會確保下列項目出現在 <專案根目錄>/.gitignore：
    ai-usage-log.config.json          個人設定（姓名、資料夾）
    <output_dir>/.ai-usage-log-state.json   處理進度
    <output_dir>/.draft/              草稿工作檔

沒有 .gitignore 就建立；已經有的行不重複加；只在結尾追加一個區塊。
輸出：新增了哪些行（沒有新增就印「已是最新」）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MARK = "# ai-usage-log（個人檔案，不要提交）"


def wanted_entries(project: Path, output_dir: str) -> list[str]:
    entries = ["ai-usage-log.config.json"]
    out = (project / output_dir).resolve()
    try:
        rel = out.relative_to(project.resolve()).as_posix()
    except ValueError:
        rel = None  # 輸出資料夾在專案外，不需要（也不能）寫進這個 .gitignore
    if rel is not None:
        prefix = "" if rel in ("", ".") else rel + "/"
        entries += [f"{prefix}.ai-usage-log-state.json", f"{prefix}.draft/"]
    return entries


def _norm(line: str) -> str:
    return line.strip().lstrip("/")


def ensure(project: Path, output_dir: str = "ai-log") -> list[str]:
    gi = Path(project) / ".gitignore"
    raw = gi.read_bytes() if gi.exists() else b""
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig") if raw else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    present = {_norm(l) for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")}
    missing = [e for e in wanted_entries(Path(project), output_dir) if _norm(e) not in present]
    if not missing:
        return []
    add = ([nl] if text and not text.endswith(("\n", "\r")) else []) + ([nl] if text.strip() else [])
    block = nl.join([MARK, *missing]) + nl
    new = text + "".join(add) + block
    gi.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new.encode("utf-8"))
    return missing


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--output-dir", default="ai-log")
    a = ap.parse_args(argv)
    added = ensure(Path(a.project), a.output_dir)
    if added:
        print("已寫入 .gitignore：" + "、".join(added))
    else:
        print(".gitignore 已是最新，沒有變更。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
