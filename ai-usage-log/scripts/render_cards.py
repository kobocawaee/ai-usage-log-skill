"""把對話中的關鍵訊息排版成「卡片」圖片（SPEC 第 5 節）。

用法：
    python render_cards.py conversation.json cards.json out_dir [--html-only] [--theme light|dark] [--overwrite]

已有同名圖片時不會覆蓋，印出清單並回傳 3；確定要取代才加 --overwrite。

conversation.json：parse_session.py 的輸出。
cards.json：
    {
      "header": "Claude Code＋**/bmad-prd**｜2026-10-30",  # 純文字（會跳脫）；**包住的部分**顯示粗體
      "source": "<session-id>.jsonl",
      "member_name": "王小明",
      "file_prefix": "1030_PRD_王小明",
      "cards": [ {"no": "01", "title": "下達指令", "kind": "人的輸入", "messages": [0, 1]}, ... ]
    }
    kind：人的輸入｜人工決策｜AI 產出

找不到 Playwright / Chromium 時，改為只輸出 HTML 並提示安裝指令，不會讓流程失敗。
Markdown 一律用 markdown-it-py 的 CommonMark 模式（理由見 SPEC 5.2）。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import redact  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "card.html"
KIND_CLASS = {"人的輸入": "i", "人工決策": "h", "AI 產出": "a"}
ILLEGAL_NAME = re.compile(r'[\\/:*?"<>|\s]')
INSTALL_HINT = ("找不到 Playwright 或 Chromium，已改為只輸出 HTML。\n"
                "請執行：pip install playwright 以及 python -m playwright install chromium")

# html=False：訊息中若出現 <div> 之類的文字，要原樣顯示，不能被當成 HTML 解讀（內容忠實性）
_MD = MarkdownIt("commonmark", {"html": False}).enable("table")
# 人的訊息：單一換行也要保留（使用者常用換行分條列，CommonMark 預設會把它併成一行）
_MD_USER = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table")

_ORDERED = re.compile(r"^(\s*)(\d+)([.)])( |\t)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def escape_ordered_lists(text: str) -> str:
    """SPEC 5.2 陷阱 1：人的訊息中行首的「9. 」會被當成有序清單並重新編號，改成「9\\. 」保持原樣。
    程式碼區塊內不處理（否則會多出反斜線）。"""
    out, in_fence = [], False
    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            line = _ORDERED.sub(lambda m: f"{m.group(1)}{m.group(2)}\\{m.group(3)}{m.group(4)}", line)
        out.append(line)
    return "\n".join(out)


def to_html(text: str, role: str) -> str:
    if role == "user":
        return _MD_USER.render(escape_ordered_lists(text))
    return _MD.render(text)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(fragment: str) -> str:
    p = _TextExtractor()
    p.feed(fragment)
    return "".join(p.parts)


def local_label(msg: dict) -> str:
    return msg.get("local", "")


THEMES = ("light", "dark")


def build_card(conv: list[dict], meta: dict, card: dict, theme: str = "light") -> tuple[str, bool]:
    """回傳 (完整 HTML, 是否有遮罩)。"""
    if theme not in THEMES:
        raise ValueError(f"未知的主題：{theme}（可用：{', '.join(THEMES)}）")
    if card["kind"] not in KIND_CLASS:
        raise ValueError(f"未知的類型標籤：{card['kind']}（可用：{', '.join(KIND_CLASS)}）")
    body, masked = "", False
    for i in card["messages"]:
        m = conv[i]
        text, changed = redact(m["text"])
        masked = masked or changed
        who = meta["member_name"] if m["role"] == "user" else "AI"
        body += (f"<div class='msg {m['role']}'><div class='who'>{html.escape(who)}　{html.escape(local_label(m))}</div>"
                 f"{to_html(text, m['role'])}</div>")
    foot = f"來源：{html.escape(meta['source'])}"
    if masked:
        foot += "　｜　已遮罩敏感資訊"
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, val in {
        "THEME": "dark" if theme == "dark" else "",
        "HEADER": header_html(meta["header"]),
        "NO": html.escape(card["no"]),
        "TITLE": html.escape(card["title"]),
        "KIND_CLASS": KIND_CLASS[card["kind"]],
        "KIND": html.escape(card["kind"]),
        "BODY": body,
        "FOOT": foot,
    }.items():
        page = page.replace("{{" + key + "}}", val)
    return page, masked


def header_html(header: str) -> str:
    """頁首文字：先跳脫，再把 **文字** 轉成粗體（例如把 skill 名稱標粗體）。"""
    return re.sub(r"\*\*(.+?)\*\*", lambda m: f"<b>{m.group(1)}</b>", html.escape(header))


def card_basename(meta: dict, card: dict) -> str:
    prefix = meta["file_prefix"]
    if ILLEGAL_NAME.search(prefix) or ILLEGAL_NAME.search(card["no"]):
        raise ValueError(f"檔名含不合法字元或空白：{prefix}_{card['no']}")
    return f"{prefix}_{card['no']}"


class OverwriteError(Exception):
    """目標資料夾已有同名圖片，且沒有指定 --overwrite。"""


def render(conv_path, cards_path, out_dir, html_only: bool = False, theme: str = "light",
           overwrite: bool = False) -> dict:
    conv = json.loads(Path(conv_path).read_text(encoding="utf-8-sig"))["messages"]
    meta = json.loads(Path(cards_path).read_text(encoding="utf-8-sig"))
    out = Path(out_dir)
    pages = [(card_basename(meta, c), *build_card(conv, meta, c, theme)) for c in meta["cards"]]
    ext = ".html" if html_only else ".png"
    clash = [f"{n}{ext}" for n, _, _ in pages if (out / f"{n}{ext}").exists()]
    if clash and not overwrite:
        raise OverwriteError("以下檔案已存在，未覆蓋任何檔案：" + "、".join(clash)
                             + "\n若確定要取代，請加上 --overwrite；否則請換一個 file_prefix。")
    out.mkdir(parents=True, exist_ok=True)

    result = {"png": [], "html": [], "masked": [n for n, _, m in pages if m], "fallback": False}
    pw_ctx = None
    if not html_only:
        try:
            from playwright.sync_api import sync_playwright
            pw_ctx = sync_playwright().start()
            browser = pw_ctx.chromium.launch()
        except Exception:  # 未安裝 playwright、或沒有 chromium
            if pw_ctx is not None:
                pw_ctx.stop()
            pw_ctx = None
    if pw_ctx is None:
        result["fallback"] = True
        if not html_only:
            print(INSTALL_HINT, file=sys.stderr)
        for name, page, _ in pages:
            p = out / f"{name}.html"
            p.write_text(page, encoding="utf-8")
            result["html"].append(str(p))
        return result
    try:
        pg = browser.new_page(viewport={"width": 980, "height": 800}, device_scale_factor=1.5)
        for name, page, _ in pages:
            pg.set_content(page)
            png = out / f"{name}.png"
            pg.locator("#c").screenshot(path=str(png))
            result["png"].append(str(png))
        browser.close()
    finally:
        pw_ctx.stop()
    return result


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("conversation")
    ap.add_argument("cards")
    ap.add_argument("out_dir")
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--theme", choices=THEMES, default="light", help="卡片配色（預設 light）")
    ap.add_argument("--overwrite", action="store_true", help="允許覆蓋已存在的同名圖片")
    a = ap.parse_args(argv)
    try:
        r = render(a.conversation, a.cards, a.out_dir, a.html_only, a.theme, a.overwrite)
    except OverwriteError as e:
        print(e, file=sys.stderr)
        return 3
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
