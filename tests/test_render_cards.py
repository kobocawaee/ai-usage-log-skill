import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import render_cards as rc  # noqa: E402

USER_TEXT = "1、3 照預設\n\n2. 改成 B\n9. 另外加一條\n\n- 項目一\n- 項目二"
AI_TEXT = (
    "我整理如下：\n"
    "- 第一項\n"
    "   - 巢狀 A\n"
    "   - 巢狀 B\n"
    "- 第二項\n\n"
    "說明文字：\n"
    "1. 步驟一\n"
    "2. 步驟二\n\n"
    "| 欄位 | 數量 |\n| --- | --- |\n| 問題數 | 55 → 29 |\n"
)


def conv():
    return [
        {"idx": 0, "role": "user", "ts": "2026-10-30T12:19:00Z", "local": "2026-10-30 20:19", "text": USER_TEXT, "tools": 0},
        {"idx": 1, "role": "assistant", "ts": "2026-10-30T12:20:00Z", "local": "2026-10-30 20:20", "text": AI_TEXT, "tools": 2},
    ]


META = {"header": "Claude Code＋/demo｜2026-10-30", "source": "sample.jsonl", "member_name": "王小明",
        "file_prefix": "1030_範例_王小明"}


def body_html(idx, kind="人的輸入"):
    page, masked = rc.build_card(conv(), META, {"no": "01", "title": "測試", "kind": kind, "messages": idx})
    return page, masked


def numbers(s):
    return re.findall(r"\d+", s)


def test_user_numbering_not_renumbered():
    page, _ = body_html([0])
    assert "<ol" not in page.split("class='msg user'")[1]
    text = rc.html_to_text(page.split("class='msg user'")[1])
    assert "2. 改成 B" in text and "9. 另外加一條" in text and "1、3 照預設" in text
    # 數字序列與原文一致
    assert numbers(text.split("20:19", 1)[1]) == numbers(USER_TEXT)


def test_ai_lists_not_collapsed_and_numbers_kept():
    page, _ = body_html([1], "AI 產出")
    seg = page.split("class='msg assistant'")[1]
    assert seg.count("<li>") == 4 + 2  # 2 外層 + 2 巢狀 + 2 有序
    assert "<table>" in seg
    text = rc.html_to_text(seg)
    # 有序清單的編號由 <ol> 產生、不在文字裡；其餘數字須一致，且有序清單項目數與起始編號不變
    expected = numbers(re.sub(r"(?m)^\d+\. ", "", AI_TEXT))
    assert numbers(text.split("20:20", 1)[1]) == expected
    assert seg.count("<ol>") == 1 and seg.split("<ol>")[1].count("<li>") == 2
    assert "55 → 29" in text


def test_user_line_breaks_preserved():
    page, _ = body_html([0])
    assert "<br" in page.split("class='msg user'")[1]


def test_literal_html_in_message_is_escaped():
    c = conv()
    c[0]["text"] = "請看 <div>標籤</div> 與 <script>x</script>"
    page, _ = rc.build_card(c, META, {"no": "01", "title": "t", "kind": "人的輸入", "messages": [0]})
    assert "<script>" not in page
    assert "<div>標籤</div>" in rc.html_to_text(page)


def test_code_fence_not_escaped():
    out = rc.escape_ordered_lists("1. a\n```\n2. b\n```\n3. c")
    assert out == "1\\. a\n```\n2. b\n```\n3\\. c"


def test_ordered_paren_style_kept():
    page, _ = body_html([0])
    c = conv()
    c[0]["text"] = "3) 第三\n9) 第九"
    page, _ = rc.build_card(c, META, {"no": "01", "title": "t", "kind": "人的輸入", "messages": [0]})
    assert "<ol" not in page
    assert "9) 第九" in rc.html_to_text(page)


def test_redaction_and_footer_note():
    c = conv()
    c[0]["text"] = "寄到 a@b.com，路徑 C:\\Users\\bob\\x"
    page, masked = rc.build_card(c, META, {"no": "01", "title": "t", "kind": "人的輸入", "messages": [0]})
    assert masked and "已遮罩敏感資訊" in page
    assert "a@b.com" not in page and "bob" not in page
    page2, masked2 = body_html([0])
    assert not masked2 and "已遮罩敏感資訊" not in page2


def test_kind_validation_and_filename_rules():
    with pytest.raises(ValueError):
        rc.build_card(conv(), META, {"no": "01", "title": "t", "kind": "亂寫", "messages": [0]})
    with pytest.raises(ValueError):
        rc.card_basename({**META, "file_prefix": "a b"}, {"no": "01"})
    with pytest.raises(ValueError):
        rc.card_basename({**META, "file_prefix": "a:b"}, {"no": "01"})


def _write_inputs(tmp_path):
    cj = tmp_path / "conversation.json"
    cj.write_text(json.dumps({"messages": conv()}, ensure_ascii=False), encoding="utf-8")
    kj = tmp_path / "cards.json"
    kj.write_text(json.dumps({**META, "cards": [
        {"no": "01", "title": "下達指令", "kind": "人的輸入", "messages": [0]},
        {"no": "02", "title": "AI 產出", "kind": "AI 產出", "messages": [1]}]}, ensure_ascii=False), encoding="utf-8")
    return cj, kj


def test_render_png_on_chinese_path(tmp_path):
    pytest.importorskip("playwright")
    cj, kj = _write_inputs(tmp_path)
    out = tmp_path / "輸出 資料夾"
    r = rc.render(cj, kj, out)
    if r["fallback"]:
        pytest.skip("本機沒有 Chromium")
    assert [Path(p).name for p in r["png"]] == ["1030_範例_王小明_01.png", "1030_範例_王小明_02.png"]
    for p in r["png"]:
        data = Path(p).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 5000
    assert not list(out.glob("*.html"))


def test_fallback_html_only_when_playwright_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    cj, kj = _write_inputs(tmp_path)
    r = rc.render(cj, kj, tmp_path / "o")
    assert r["fallback"] and not r["png"] and len(r["html"]) == 2
    assert "playwright install chromium" in capsys.readouterr().err
    assert "改成 B" in Path(r["html"][0]).read_text(encoding="utf-8")
