"""產生 tests/fixtures/sample.jsonl（完全虛構的範例，供測試用）。執行：python make_sample.py"""
import json
from pathlib import Path

SID = "sample"
BASE = {"cwd": r"C:\Users\demo\proj", "sessionId": SID, "isSidechain": False}


def u(ts, content, kind="human", **kw):
    o = {**BASE, "type": "user", "timestamp": ts, "message": {"role": "user", "content": content}, **kw}
    if kind:
        o["origin"] = {"kind": kind}
    return o


def a(ts, blocks, mid, model="claude-test-1", **kw):
    return {**BASE, "type": "assistant", "timestamp": ts,
            "message": {"id": mid, "role": "assistant", "model": model, "content": blocks}, **kw}


lines = [
    {"type": "queue-operation", "timestamp": "2026-10-30T11:44:00Z"},
    u("2026-10-30T11:45:53Z",
      "<command-message>demo-skill</command-message>\n<command-name>/demo-skill</command-name>\n"
      "<command-args>寫一份範例需求</command-args>"),
    a("2026-10-30T11:46:00Z", [{"type": "thinking", "thinking": "不應輸出的思考"}], "m1"),
    a("2026-10-30T11:46:01Z", [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}], "m1"),
    u("2026-10-30T11:46:02Z", [{"type": "tool_result", "tool_use_id": "t1", "content": "工具輸出不應出現"}], kind=None),
    a("2026-10-30T11:46:10Z", [{"type": "tool_use", "id": "t2", "name": "Grep", "input": {}},
                               {"type": "tool_use", "id": "t3", "name": "Glob", "input": {}}], "m2"),
    u("2026-10-30T11:46:11Z", "peer 訊息不應出現", kind="peer"),
    a("2026-10-30T11:46:20Z", [{"type": "thinking", "thinking": "x"}], "m3"),
    a("2026-10-30T11:46:21Z", [{"type": "text", "text": "我先列出三個問題：\n1. 範圍\n2. 對象"}], "m3"),
    {**BASE, "type": "assistant", "isSidechain": True, "timestamp": "2026-10-30T11:46:30Z",
     "message": {"id": "s1", "model": "claude-sub", "content": [{"type": "text", "text": "子代理內容不應出現"}]}},
    u("2026-10-30T12:19:00Z",
      [{"type": "text", "text": "<pasted_content id=\"ab12\">1、3 照預設\n2. 改成 B\n9. 另外加一條</pasted_content id=\"ab12\">"},
       {"type": "text", "text": "<system-reminder>系統提醒不應出現</system-reminder>"}]),
    a("2026-10-30T12:19:30Z", [{"type": "tool_use", "id": "t4", "name": "Write", "input": {}}], "m4"),
    a("2026-10-30T12:19:40Z", [{"type": "text", "text": "已完成，共 29 個問題。"}], "m5", model="claude-test-2"),
    u("2026-10-30T12:20:00Z", "謝謝", kind="human"),
    a("2026-10-30T12:20:05Z", [{"type": "tool_use", "id": "t5", "name": "Bash", "input": {}}], "m6"),
]
out = Path(__file__).parent / "sample.jsonl"
out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
(Path(__file__).parent / "sample" / "subagents" / "agent-a1.meta.json").write_text(
    json.dumps({"description": "範例審查子代理"}, ensure_ascii=False), encoding="utf-8")
