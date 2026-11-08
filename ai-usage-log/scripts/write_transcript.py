"""產生完整文字紀錄 .md（SPEC 第 6 節）。

用法：
    python write_transcript.py conversation.json cards.json output.md

cards.json 與 render_cards.py 共用（讀 member_name、file_prefix、cards；可選 "tool_label"）。
輸出前一律經過 redact.py 遮罩；檔案以 UTF-8 寫入。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import redact  # noqa: E402


def _cell(s: str) -> str:
    """表格儲存格內不可有換行或直線。"""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def build_transcript(conv: dict, meta: dict) -> tuple[str, bool]:
    stats = conv["stats"]
    msgs = conv["messages"]
    masked_any = False

    def rd(t: str) -> str:
        nonlocal masked_any
        out, ch = redact(t)
        masked_any = masked_any or ch
        return out

    member = meta.get("member_name", "")
    tool_label = meta.get("tool_label") or "Claude Code"
    commands = "、".join(stats.get("commands") or []) or "（無）"
    start, end = stats.get("start_local") or "", stats.get("end_local") or ""
    time_range = start if start == end else f"{start} ～ {end[11:] if end[:10] == start[:10] else end}"

    L: list[str] = []
    L.append(f"# AI 對話紀錄：{meta.get('header', conv.get('session_id', ''))}")
    L.append("")
    L.append(f"本檔由 Claude Code 原始對話紀錄（`{conv['source_file']}`）轉出，只保留人與 AI 的對話文字，"
             "不含 AI 的思考過程與工具操作細節（以次數表示）。內容未經修改，僅清除 Claude Code 自動加上的標記，"
             "並遮罩敏感資訊（金鑰、email、使用者家目錄、密碼）。")
    L.append("")
    L.append("## 基本資訊")
    L.append("")
    L.append("| 項目 | 內容 |")
    L.append("| --- | --- |")
    for k, v in [
        ("日期與時間範圍", time_range),
        ("操作者", member),
        ("工具", tool_label),
        ("模型", "、".join(stats.get("models") or []) or "（未記錄）"),
        ("使用的 skill／指令", commands),
        ("對話規模", f"人工輸入 {stats['human_inputs']} 次、AI 回覆 {stats['assistant_replies']} 則、"
                     f"工具操作 {stats['tool_uses']} 次"),
        ("子代理數量", stats["subagent_count"]),
    ]:
        L.append(f"| {k} | {_cell(rd(str(v)))} |")
    L.append("")

    L.append("## 子代理")
    L.append("")
    if conv.get("subagents"):
        L.append("| 編號 | 任務名稱 |")
        L.append("| --- | --- |")
        for i, s in enumerate(conv["subagents"], 1):
            L.append(f"| {i} | {_cell(rd(s['description']))} |")
    else:
        L.append("（本次對話沒有子代理）")
    L.append("")

    cards = meta.get("cards") or []
    L.append("## 關鍵節點")
    L.append("")
    if cards:
        L.append("| 時間 | 節點 | 類型 | 對應圖片 |")
        L.append("| --- | --- | --- | --- |")
        for c in cards:
            first = msgs[c["messages"][0]]["local"] if c["messages"] else ""
            img = f"{meta.get('image_dir', '').rstrip('/')}/{meta['file_prefix']}_{c['no']}.png".lstrip("/")
            L.append(f"| {first} | {c['no']} {_cell(rd(c['title']))} | {c['kind']} | {img} |")
    else:
        L.append("（尚未指定關鍵節點）")
    L.append("")

    L.append("## 完整對話")
    L.append("")
    for m in msgs:
        who = member if m["role"] == "user" else "AI"
        text = rd(m["text"])
        if m["role"] == "user":
            L.append(f"### {m['local']}　{who}")
            L.append("")
            L.extend("> " + ln if ln else ">" for ln in text.split("\n"))
        else:
            L.append(f"### {m['local']}　{who}")
            L.append("")
            if m["tools"]:
                L.append(f"（AI 執行了 {m['tools']} 次工具操作）")
                L.append("")
            if text:
                L.append(text)
        L.append("")
    return "\n".join(L).rstrip() + "\n", masked_any


def write_transcript(conv_path, cards_path, out_path) -> Path:
    conv = json.loads(Path(conv_path).read_text(encoding="utf-8"))
    meta = json.loads(Path(cards_path).read_text(encoding="utf-8"))
    md, _ = build_transcript(conv, meta)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("conversation")
    ap.add_argument("cards")
    ap.add_argument("output")
    a = ap.parse_args(argv)
    print(f"已輸出 {write_transcript(a.conversation, a.cards, a.output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
