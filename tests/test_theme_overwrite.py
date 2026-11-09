import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import render_cards as rc  # noqa: E402

CONV = [{"idx": 0, "role": "user", "local": "2026-10-30 20:19", "text": "hi", "tools": 0}]
META = {"header": "Claude Code｜2026-10-30", "source": "s.jsonl", "member_name": "王小明", "file_prefix": "p",
        "cards": [{"no": "01", "title": "t", "kind": "人的輸入", "messages": [0]}]}


def files(tmp_path):
    c = tmp_path / "c.json"
    k = tmp_path / "k.json"
    c.write_text(json.dumps({"messages": CONV}, ensure_ascii=False), encoding="utf-8")
    k.write_text(json.dumps(META, ensure_ascii=False), encoding="utf-8")
    return c, k


def test_json_with_bom_is_accepted(tmp_path):
    # Windows 記事本存檔會加 BOM；不能因此讀不進去
    c, k = files(tmp_path)
    k.write_text(json.dumps(META, ensure_ascii=False), encoding="utf-8-sig")
    out = tmp_path / "images"
    assert rc.main([str(c), str(k), str(out), "--html-only"]) == 0


def test_light_is_default_and_dark_adds_class():
    card = META["cards"][0]
    assert '<body class="">' in rc.build_card(CONV, META, card)[0]
    assert '<body class="dark">' in rc.build_card(CONV, META, card, "dark")[0]


def test_unknown_theme_rejected():
    with pytest.raises(ValueError):
        rc.build_card(CONV, META, META["cards"][0], "neon")


def test_existing_image_is_not_overwritten(tmp_path):
    c, k = files(tmp_path)
    out = tmp_path / "images"
    out.mkdir()
    (out / "p_01.html").write_text("OLD", encoding="utf-8")
    with pytest.raises(rc.OverwriteError) as e:
        rc.render(c, k, out, html_only=True)
    assert "p_01.html" in str(e.value)
    assert (out / "p_01.html").read_text(encoding="utf-8") == "OLD"
    assert rc.main([str(c), str(k), str(out), "--html-only"]) == 3
    assert (out / "p_01.html").read_text(encoding="utf-8") == "OLD"


def test_overwrite_flag_replaces_and_dark_applies(tmp_path):
    c, k = files(tmp_path)
    out = tmp_path / "images"
    out.mkdir()
    (out / "p_01.html").write_text("OLD", encoding="utf-8")
    assert rc.main([str(c), str(k), str(out), "--html-only", "--overwrite", "--theme", "dark"]) == 0
    assert 'class="dark"' in (out / "p_01.html").read_text(encoding="utf-8")
