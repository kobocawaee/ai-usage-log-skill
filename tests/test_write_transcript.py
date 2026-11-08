import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-usage-log" / "scripts"))
import parse_session as ps  # noqa: E402
import write_transcript as wt  # noqa: E402

META = {
    "header": "Claude Code＋/demo-skill｜2026-10-30",
    "member_name": "王小明",
    "file_prefix": "1030_範例_王小明",
    "cards": [{"no": "01", "title": "下達指令", "kind": "人的輸入", "messages": [0]},
              {"no": "02", "title": "回答問題", "kind": "人工決策", "messages": [2]}],
}


def build():
    conv = ps.parse_session(ROOT / "tests" / "fixtures" / "sample.jsonl")
    return conv, wt.build_transcript(conv, META)[0]


def test_sections_and_basic_info():
    _, md = build()
    for h in ("## 基本資訊", "## 子代理", "## 關鍵節點", "## 完整對話"):
        assert h in md
    assert "未經修改" in md and "sample.jsonl" in md
    assert "人工輸入 3 次、AI 回覆 2 則、工具操作 5 次" in md
    assert "範例審查子代理" in md
    assert "claude-test-1、claude-test-2" in md
    assert "/demo-skill" in md
    assert "2026-10-30 19:45 ～ 20:20" in md


def test_key_nodes_table_links_images():
    _, md = build()
    assert "| 2026-10-30 19:45 | 01 下達指令 | 人的輸入 | 1030_範例_王小明_01.png |" in md
    assert "| 2026-10-30 20:19 | 02 回答問題 | 人工決策 | 1030_範例_王小明_02.png |" in md


def test_dialogue_format_and_no_tool_details():
    _, md = build()
    body = md.split("## 完整對話")[1]
    assert "> 1、3 照預設" in body and "> 2. 改成 B" in body and "> 9. 另外加一條" in body
    assert "（AI 執行了 3 次工具操作）" in body
    assert "（AI 執行了 1 次工具操作）" in body
    assert "我先列出三個問題：" in body
    for leak in ("不應輸出", "工具輸出", "子代理內容", "<system-reminder>", "<pasted_content"):
        assert leak not in md


def test_redaction_applied():
    conv, _ = build()
    conv["messages"][0]["text"] = "信箱 a@b.com 路徑 C:\\Users\\bob\\x"
    md = wt.build_transcript(conv, META)[0]
    assert "a@b.com" not in md and "bob" not in md and "[email]" in md


def test_write_utf8_on_chinese_path(tmp_path):
    conv = ps.parse_session(ROOT / "tests" / "fixtures" / "sample.jsonl")
    cj, kj = tmp_path / "c.json", tmp_path / "k.json"
    cj.write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")
    kj.write_text(json.dumps(META, ensure_ascii=False), encoding="utf-8")
    out = wt.write_transcript(cj, kj, tmp_path / "輸出" / "1030_範例_王小明_對話紀錄.md")
    assert "我先列出三個問題" in out.read_text(encoding="utf-8")


def test_key_nodes_use_image_subfolder():
    conv = ps.parse_session(ROOT / "tests" / "fixtures" / "sample.jsonl")
    md = wt.build_transcript(conv, {**META, "image_dir": "images"})[0]
    assert "| 人的輸入 | images/1030_範例_王小明_01.png |" in md
