"""把 Claude Code 的 .jsonl 對話紀錄轉成清理後的 conversation.json（SPEC 第 3 節）。

用法：
    python parse_session.py <session.jsonl> [-o conversation.json] [--tz Asia/Taipei]

輸出 JSON：
    {
      "session_id": "...", "source_file": "xxx.jsonl", "cwd": "...", "timezone": "Asia/Taipei",
      "stats": {...},
      "subagents": [{"id": "...", "description": "..."}],
      "messages": [{"idx": 0, "role": "user"|"assistant", "ts": "<UTC ISO>", "local": "YYYY-MM-DD HH:MM",
                    "text": "...", "tools": 0}, ...]
    }

只使用標準函式庫。所有檔案讀寫一律明確指定 UTF-8。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Taipei"

# 整段（含內容）刪除的系統標記
_DROP_BLOCK_TAGS = (
    "system-reminder",
    "command-message",
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
)


def clean_text(text: str) -> str:
    """SPEC 3.3：清掉 Claude Code 自動加上的標記。"""
    # 斜線指令：<command-name>/x</command-name><command-args>參數</command-args> → 「/x 參數」
    # 必須先處理，因為 command-message 之後會被整段刪除。
    text = re.sub(
        r"<command-name>(.*?)</command-name>\s*(?:<command-args>(.*?)</command-args>)?",
        lambda m: (m.group(1).strip() + " " + (m.group(2) or "").strip()).strip() + "\n",
        text,
        flags=re.S,
    )
    for tag in _DROP_BLOCK_TAGS:
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}\s*>\s*", "", text, flags=re.S)
    # 貼上的長文字：只刪標籤，保留內容（開頭與結尾標籤都帶 id）
    text = re.sub(r"</?pasted_content\b[^>]*>", "", text)
    # 清理後可能留下過多空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def to_local(ts: str, tz: ZoneInfo) -> dt.datetime:
    return parse_ts(ts).astimezone(tz)


def _text_blocks(content) -> list[str]:
    """message.content 可能是字串或陣列；只取 type == text 的文字。"""
    if isinstance(content, str):
        return [content]
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                out.append(b["text"])
    return out


def read_lines(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # 單行損毀（例如寫入到一半被中斷）不應讓整個流程失敗
                print(f"警告：{path.name} 第 {n} 行不是合法 JSON，已略過", file=sys.stderr)


def read_subagents(jsonl_path: Path) -> list[dict]:
    """SPEC 3.4：只讀 subagents/*.meta.json 的 description。"""
    sub_dir = jsonl_path.with_suffix("") / "subagents"
    result = []
    if sub_dir.is_dir():
        for meta in sorted(sub_dir.glob("*.meta.json")):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            agent_id = meta.name[: -len(".meta.json")]
            if agent_id.startswith("agent-"):
                agent_id = agent_id[len("agent-"):]
            result.append({"id": agent_id, "description": str(data.get("description", "")).strip()})
    return result


def parse_session(jsonl_path: Path, tz_name: str = DEFAULT_TZ) -> dict:
    jsonl_path = Path(jsonl_path)
    tz = ZoneInfo(tz_name)

    session_id = jsonl_path.stem
    cwd = None
    models: list[str] = []
    commands: list[str] = []
    # 暫存：assistant 的一則 API 訊息常被拆成多行（thinking / text / tool_use 各一行，
    # 共用 message.id），要合併起來才算「一則回覆」。
    entries: list[dict] = []
    pending_tools = 0  # 尚未歸屬到任何 assistant 文字回覆的工具操作次數
    total_tools = 0
    cur_asst: dict | None = None  # 目前正在累積的 assistant 訊息 {key, texts, ts}

    def flush_assistant():
        nonlocal cur_asst, pending_tools
        if cur_asst is None:
            return
        text = "\n\n".join(t for t in cur_asst["texts"] if t.strip()).strip()
        if text:
            entries.append({"role": "assistant", "ts": cur_asst["ts"], "text": text, "tools": pending_tools})
            pending_tools = 0
        cur_asst = None

    def flush_trailing_tools(ts_fallback: str):
        """工具操作之後沒有文字回覆時，補一筆空文字的 assistant 紀錄，避免工具次數消失。"""
        nonlocal pending_tools
        if pending_tools:
            entries.append({"role": "assistant", "ts": ts_fallback, "text": "", "tools": pending_tools})
            pending_tools = 0

    last_ts = None
    for obj in read_lines(jsonl_path):
        typ = obj.get("type")
        if typ not in ("user", "assistant"):
            continue
        if obj.get("isSidechain"):
            continue  # 子代理的訊息
        ts = obj.get("timestamp")
        if not ts:
            continue
        if cwd is None and obj.get("cwd"):
            cwd = obj["cwd"]
        if obj.get("sessionId") and session_id == jsonl_path.stem:
            session_id = obj["sessionId"]
        msg = obj.get("message") or {}

        if typ == "user":
            origin = (obj.get("origin") or {}).get("kind")
            if origin != "human":
                continue  # 工具結果、task-notification、peer 等
            flush_assistant()
            raw = "\n".join(_text_blocks(msg.get("content")))
            for m in re.finditer(r"<command-name>(.*?)</command-name>", raw, flags=re.S):
                name = m.group(1).strip()
                if name and name not in commands:
                    commands.append(name)
            text = clean_text(raw)
            if not text:
                continue
            flush_trailing_tools(last_ts or ts)
            entries.append({"role": "user", "ts": ts, "text": text, "tools": 0})
            last_ts = ts
        else:
            key = msg.get("id") or obj.get("uuid")
            if cur_asst is not None and cur_asst["key"] != key:
                flush_assistant()
            if cur_asst is None:
                cur_asst = {"key": key, "texts": [], "ts": ts}
            model = msg.get("model")
            if model and model != "<synthetic>" and model not in models:
                models.append(model)
            content = msg.get("content")
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and isinstance(b.get("text"), str):
                        cur_asst["texts"].append(b["text"])
                    elif b.get("type") == "tool_use":
                        pending_tools += 1
                        total_tools += 1
            elif isinstance(content, str):
                cur_asst["texts"].append(content)
            last_ts = ts
    flush_assistant()
    flush_trailing_tools(last_ts or "1970-01-01T00:00:00Z")

    messages = []
    for i, e in enumerate(entries):
        e["idx"] = i
        e["local"] = to_local(e["ts"], tz).strftime("%Y-%m-%d %H:%M")
        messages.append({k: e[k] for k in ("idx", "role", "ts", "local", "text", "tools")})

    subagents = read_subagents(jsonl_path)
    stamps = [e["ts"] for e in entries]
    start = min(stamps, key=parse_ts) if stamps else None
    end = max(stamps, key=parse_ts) if stamps else None
    stats = {
        "start_utc": start,
        "end_utc": end,
        "start_local": to_local(start, tz).strftime("%Y-%m-%d %H:%M") if start else None,
        "end_local": to_local(end, tz).strftime("%Y-%m-%d %H:%M") if end else None,
        "human_inputs": sum(1 for e in entries if e["role"] == "user"),
        "assistant_replies": sum(1 for e in entries if e["role"] == "assistant" and e["text"]),
        "tool_uses": total_tools,
        "models": models,
        "commands": commands,
        "subagent_count": len(subagents),
    }
    return {
        "session_id": session_id,
        "source_file": jsonl_path.name,
        "cwd": cwd,
        "timezone": tz_name,
        "stats": stats,
        "subagents": subagents,
        "messages": messages,
    }


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Claude Code .jsonl → conversation.json")
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="輸出路徑；省略則寫到 stdout")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"顯示時區（預設 {DEFAULT_TZ}）")
    args = ap.parse_args(argv)
    if not args.jsonl.is_file():
        print(f"找不到檔案：{args.jsonl}", file=sys.stderr)
        return 1
    result = parse_session(args.jsonl, args.tz)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        s = result["stats"]
        print(f"已輸出 {args.output}（人工輸入 {s['human_inputs']}、AI 回覆 {s['assistant_replies']}、"
              f"工具操作 {s['tool_uses']}、子代理 {s['subagent_count']}）")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
