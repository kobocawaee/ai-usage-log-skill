import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import find_ai_log as fa  # noqa: E402


def test_none_found(tmp_path):
    (tmp_path / "docs").mkdir()
    assert fa.find_ai_logs(tmp_path) == []


def test_root_ai_log_first_then_nested(tmp_path):
    (tmp_path / "ai-log").mkdir()
    (tmp_path / "sports-center" / "ai-log").mkdir(parents=True)
    assert fa.find_ai_logs(tmp_path) == ["ai-log", "sports-center/ai-log"]


def test_only_nested_and_case_insensitive(tmp_path):
    (tmp_path / "sports-center" / "AI-LOG").mkdir(parents=True)
    assert fa.find_ai_logs(tmp_path) == ["sports-center/AI-LOG"]


def test_skips_irrelevant_folders_and_depth_limit(tmp_path):
    (tmp_path / "node_modules" / "x" / "ai-log").mkdir(parents=True)
    (tmp_path / "venv" / "ai-log").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "d" / "ai-log").mkdir(parents=True)  # 太深
    assert fa.find_ai_logs(tmp_path) == []
    assert fa.find_ai_logs(tmp_path, depth=6) == ["a/b/c/d/ai-log"]


def test_does_not_look_inside_ai_log(tmp_path):
    (tmp_path / "ai-log" / "ai-log").mkdir(parents=True)
    assert fa.find_ai_logs(tmp_path) == ["ai-log"]


def test_cli_prints_json(tmp_path, capsys):
    (tmp_path / "ai-log").mkdir()
    assert fa.main(["--project", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["found"] == ["ai-log"]
