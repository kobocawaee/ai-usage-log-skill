import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import ensure_gitignore as eg  # noqa: E402


def test_creates_gitignore_when_missing(tmp_path):
    added = eg.ensure(tmp_path, "ai-log")
    assert added == ["ai-usage-log.config.json", "ai-log/.ai-usage-log-state.json", "ai-log/.draft/"]
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert eg.MARK in text and "ai-log/.draft/" in text


def test_appends_without_touching_existing_and_is_idempotent(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n.env", encoding="utf-8")  # 結尾沒有換行
    eg.ensure(tmp_path, "ai-log")
    text = gi.read_text(encoding="utf-8")
    assert text.startswith("node_modules/\n.env\n")
    before = text
    assert eg.ensure(tmp_path, "ai-log") == []
    assert gi.read_text(encoding="utf-8") == before


def test_skips_lines_already_present_even_with_leading_slash(tmp_path):
    (tmp_path / ".gitignore").write_text("/ai-usage-log.config.json\n", encoding="utf-8")
    assert "ai-usage-log.config.json" not in eg.ensure(tmp_path, "ai-log")


def test_keeps_bom_and_crlf(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_bytes(b"\xef\xbb\xbfa.txt\r\n")
    eg.ensure(tmp_path, "ai-log")
    raw = gi.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")


def test_nested_and_outside_output_dir(tmp_path):
    assert "sports-center/ai-log/.draft/" in eg.ensure(tmp_path, "sports-center/ai-log")
    other = tmp_path / "p2"
    other.mkdir()
    assert eg.ensure(other, "../elsewhere") == ["ai-usage-log.config.json"]  # 專案外的資料夾不寫
