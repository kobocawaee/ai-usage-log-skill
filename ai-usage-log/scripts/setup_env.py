r"""準備 skill 專用的 Python 環境（不碰系統 Python）。只用標準函式庫，可用任何 Python 3.10+ 執行。

用法：
    python setup_env.py           # 確保環境存在且套件齊全（缺什麼補什麼），最後一行印出該環境的 python 路徑
    python setup_env.py --check   # 只檢查：齊全就印出 python 路徑並回傳 0，否則回傳 1（不安裝任何東西）
    python setup_env.py --force   # 重建環境

環境位置：~/.claude/ai-usage-log-venv（Windows 為 %USERPROFILE%\.claude\ai-usage-log-venv）。
可用環境變數 AI_USAGE_LOG_VENV 改位置。環境放在 skill 資料夾之外，更新或重裝 skill 不必重建。
進度訊息一律寫到 stderr；stdout 最後一行才是 python 路徑，方便程式擷取。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
IMPORT_CHECK = "import openpyxl, markdown_it, playwright, tzdata"


def venv_dir() -> Path:
    override = os.environ.get("AI_USAGE_LOG_VENV")
    return Path(override) if override else Path(os.path.expanduser("~")) / ".claude" / "ai-usage-log-venv"


def venv_python(d: Path) -> Path:
    return d / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def packages_ok(py: Path) -> bool:
    if not py.exists():
        return False
    r = subprocess.run([str(py), "-I", "-c", IMPORT_CHECK], capture_output=True)
    return r.returncode == 0


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def ensure(force: bool = False) -> Path:
    if sys.version_info < (3, 10):
        raise SystemExit("需要 Python 3.10 以上")
    d = venv_dir()
    py = venv_python(d)
    if force and d.exists():
        shutil.rmtree(d)
    if packages_ok(py):
        return py
    if not py.exists():
        log(f"建立專用環境：{d}")
        d.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(d)
    log("安裝套件（第一次約需一兩分鐘）……")
    subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
                   check=True, stdout=sys.stderr)
    log("安裝 Chromium（截圖用；已安裝則很快）……")
    r = subprocess.run([str(py), "-m", "playwright", "install", "chromium"], stdout=sys.stderr)
    if r.returncode != 0:
        log("Chromium 安裝失敗：圖片會退回只輸出 HTML。可稍後手動執行：\n"
            f'  "{py}" -m playwright install chromium')
    if not packages_ok(py):
        raise SystemExit("套件安裝後仍無法匯入，請檢查上方訊息")
    return py


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        py = venv_python(venv_dir())
        if packages_ok(py):
            print(py)
            return 0
        log("環境尚未準備好，請執行：python setup_env.py")
        return 1
    py = ensure(a.force)
    print(py)
    return 0


if __name__ == "__main__":
    sys.exit(main())
