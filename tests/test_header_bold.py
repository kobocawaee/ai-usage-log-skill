import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import render_cards as rc  # noqa: E402


def test_bold_markup_in_header():
    assert rc.header_html("Claude Code＋**/bmad-prd**｜2026-10-30") == "Claude Code＋<b>/bmad-prd</b>｜2026-10-30"


def test_header_without_markup_unchanged_and_html_escaped():
    assert rc.header_html("Claude Code｜2026-10-30") == "Claude Code｜2026-10-30"
    assert rc.header_html("a <script>x</script> **b**") == "a &lt;script&gt;x&lt;/script&gt; <b>b</b>"


def test_card_contains_bold_header():
    conv = [{"idx": 0, "role": "user", "local": "2026-10-30 20:19", "text": "hi", "tools": 0}]
    meta = {"header": "Claude Code＋**/demo**｜2026-10-30", "source": "s.jsonl", "member_name": "王小明",
            "file_prefix": "p"}
    page, _ = rc.build_card(conv, meta, {"no": "01", "title": "t", "kind": "人的輸入", "messages": [0]})
    assert "AI 使用紀錄節錄｜Claude Code＋<b>/demo</b>｜2026-10-30" in page
