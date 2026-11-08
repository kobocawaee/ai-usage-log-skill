r"""敏感資訊遮罩（SPEC 5.3）。圖片與文字紀錄在輸出前都要先經過這裡。

    from redact import redact
    new_text, changed = redact(text)

規則（依序套用）：
  1. 密碼類欄位  password=… / PASSWORD: …     → password=[已遮罩]
  2. Email                                    → [email]
  3. 使用者家目錄 C:\Users\名稱、/home/名稱、/Users/名稱 → ~
  4. API 金鑰／token：sk-、ghp_、gho_、xox[bp]-、長度 ≥ 32 的英數字串（含 -_）→ [已遮罩]

設計取捨（SPEC 沒寫細節，自行決定，見 repo issue）：
  - 通用的「長度 ≥ 32」規則要求字串同時含英文字母與數字，否則長的 snake_case 識別字、
    連續底線或連字號會被誤遮罩，破壞內容忠實性。
  - 標準 UUID（8-4-4-4-12）不是祕密（session id、檔名常見），不遮罩。
"""
from __future__ import annotations

import re

MASK = "[已遮罩]"

_PASSWORD = re.compile(
    r"(?i)\b(pass(?:word|wd)?|pwd)\b(\s*[=:：]\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_HOME_WIN = re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"'<>|:*?]+")
_HOME_UNIX = re.compile(r"(?<![\w.])/(?:home|Users)/[^/\s\"'<>|:*?]+")
_PREFIXED_KEY = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{8,}|gh[po]_[A-Za-z0-9]{8,}|xox[bp]-[A-Za-z0-9\-]{8,})")
_LONG = re.compile(r"(?<![A-Za-z0-9_\-])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9_\-])")
_UUID = re.compile(r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _long_repl(m: re.Match) -> str:
    s = m.group(0)
    if _UUID.match(s):
        return s
    if re.search(r"[A-Za-z]", s) and re.search(r"\d", s):
        return MASK
    return s


def redact(text: str) -> tuple[str, bool]:
    """回傳 (遮罩後文字, 是否有變動)。"""
    out = _PASSWORD.sub("password=" + MASK, text)
    out = _EMAIL.sub("[email]", out)
    out = _HOME_WIN.sub("~", out)
    out = _HOME_UNIX.sub("~", out)
    out = _PREFIXED_KEY.sub(MASK, out)
    out = _LONG.sub(_long_repl, out)
    return out, out != text
