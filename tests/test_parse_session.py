import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-usage-log" / "scripts"))

import parse_session as ps  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample.jsonl"


def result(tz="Asia/Taipei"):
    return ps.parse_session(FIXTURE, tz)


def test_human_and_ai_separated_no_leaks():
    r = result()
    blob = json.dumps(r["messages"], ensure_ascii=False)
    for leak in ("不應輸出", "不應出現", "子代理內容", "tool_result"):
        assert leak not in blob
    roles = [m["role"] for m in r["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]


def test_markup_cleaning():
    msgs = result()["messages"]
    assert msgs[0]["text"] == "/demo-skill 寫一份範例需求"
    assert msgs[2]["text"] == "1、3 照預設\n2. 改成 B\n9. 另外加一條"  # 標籤刪除、內容逐字保留
    assert "<" not in msgs[2]["text"]


def test_tool_counts_and_stats():
    r = result()
    assert r["stats"]["tool_uses"] == 5
    assert [m["tools"] for m in r["messages"]] == [0, 3, 0, 1, 0, 1]
    # 最後一筆是只有工具操作、沒有文字的回覆
    assert r["messages"][-1]["text"] == ""
    s = r["stats"]
    assert s["human_inputs"] == 3
    assert s["assistant_replies"] == 2
    assert s["models"] == ["claude-test-1", "claude-test-2"]
    assert s["commands"] == ["/demo-skill"]
    assert s["subagent_count"] == 1
    assert r["subagents"] == [{"id": "a1", "description": "範例審查子代理"}]
    assert r["session_id"] == "sample"
    assert r["cwd"] == r"C:\Users\demo\proj"


def test_timezone_conversion():
    r = result("Asia/Taipei")
    assert r["messages"][0]["local"] == "2026-10-30 19:45"
    assert r["messages"][0]["ts"] == "2026-10-30T11:45:53Z"
    assert r["stats"]["start_local"] == "2026-10-30 19:45"
    assert r["stats"]["end_local"] == "2026-10-30 20:20"
    assert result("UTC")["messages"][0]["local"] == "2026-10-30 11:45"
    # 跨日：UTC 17:00 在台北是隔天 01:00
    assert ps.to_local("2026-10-30T17:00:00Z", ps.ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M") == "2026-10-31 01:00"


def test_clean_text_variants():
    assert ps.clean_text("<command-name>/x</command-name><command-args></command-args>") == "/x"
    assert ps.clean_text("a<system-reminder>\nzzz\n</system-reminder>b") == "ab"
    assert ps.clean_text("<local-command-stdout>out</local-command-stdout>hi") == "hi"


def test_cli_writes_utf8_on_chinese_path(tmp_path):
    out_dir = tmp_path / "中文 資料夾"
    out = out_dir / "對話.json"
    assert ps.main([str(FIXTURE), "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["messages"][1]["text"].startswith("我先列出三個問題")


def test_bad_line_is_skipped(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(FIXTURE.read_text(encoding="utf-8") + "{壞掉的行\n", encoding="utf-8")
    assert len(ps.parse_session(p)["messages"]) == 6


def test_missing_file_returns_error(tmp_path):
    assert ps.main([str(tmp_path / "nope.jsonl")]) == 1
