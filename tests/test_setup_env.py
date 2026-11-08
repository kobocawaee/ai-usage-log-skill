import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-usage-log" / "scripts"))
import setup_env as se  # noqa: E402


def test_default_location_outside_skill_folder(monkeypatch):
    monkeypatch.delenv("AI_USAGE_LOG_VENV", raising=False)
    d = se.venv_dir()
    assert d.name == "ai-usage-log-venv" and d.parent.name == ".claude"
    assert not str(d).startswith(str(ROOT))


def test_env_override_and_python_path(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_USAGE_LOG_VENV", str(tmp_path / "v"))
    assert se.venv_dir() == tmp_path / "v"
    p = se.venv_python(tmp_path / "v")
    assert p.name == ("python.exe" if os.name == "nt" else "python")


def test_check_fails_when_missing_and_installs_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AI_USAGE_LOG_VENV", str(tmp_path / "nope"))
    assert se.main(["--check"]) == 1
    assert not (tmp_path / "nope").exists()


def test_check_passes_on_dev_venv(monkeypatch, capsys):
    dev = ROOT / ".venv"
    if not se.venv_python(dev).exists():
        return
    monkeypatch.setenv("AI_USAGE_LOG_VENV", str(dev))
    assert se.main(["--check"]) == 0
    assert capsys.readouterr().out.strip().endswith("python.exe" if os.name == "nt" else "python")
