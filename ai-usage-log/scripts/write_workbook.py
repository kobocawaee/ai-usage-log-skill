"""建立或附加 AI 使用紀錄表 .xlsx（SPEC 第 4 節），並更新狀態檔（第 7 節）。

用法：
    python write_workbook.py draft.json --config ai-usage-log.config.json

draft.json：
    {
      "session_id": "abcd1234-....",
      "outputs": ["ai-log/1030_PRD_王小明_01.png", ...],       # 寫入狀態檔用（可省略）
      "rows": [
        {"date": "2026-10-30", "activity": "需求", "task": "...", "tool": "Claude Code＋bmad-prd",
         "prompt": "...", "output": "...", "judgment": "...", "adoption": "小幅修改",
         "images": ["1030_PRD_王小明_01.png"], "other_files": ["docs/prd.md"],
         "section": "B（需求）", "source": "abcd1234 19:45–20:19"}
      ]
    }
紀錄表沒有「成員」欄：每人一個檔案，檔名帶姓名即可辨識（見設定檔的 workbook）。
設定檔中的相對路徑，一律以設定檔所在資料夾（課程專案根目錄）為基準。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HEADERS = ["日期", "軟工活動", "具體工作", "AI 工具／技能", "Prompt 重點", "AI 產出摘要",
           "人工判斷與修正", "採用程度", "截圖／檔案", "對應文件章節", "來源"]
WIDTHS = [12, 10, 30, 22, 40, 40, 60, 12, 36, 16, 20]
COL_FILES, COL_SOURCE = 9, 11  # 「截圖／檔案」「來源」欄的位置（從 1 起算）
SHEET_INFO, SHEET_LOG, SHEET_OPT = "說明", "紀錄表", "選項"
VALIDATION_ROWS = 1000
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
SOURCE_RE = re.compile(r"^(\S+)\s+(\d{1,2}:\d{2})\s*[–\-～~]\s*(\d{1,2}:\d{2})$")
STATE_NAME = ".ai-usage-log-state.json"
PENDING_MARKS = ("[待確認]", "[待補理由]")


class WorkbookLocked(Exception):
    pass


# ---------- 設定 ----------
def load_config(path: Path) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))  # -sig：容忍記事本存檔的 BOM
    base = Path(path).resolve().parent
    cfg["_base"] = base
    # 沒寫 workbook 時，以姓名命名（每人一個檔案）。舊設定檔的 member／members 會被忽略。
    default_wb = f"{cfg.get('output_dir', 'ai-log')}/G-AI使用紀錄-{cfg.get('member_name', '我')}.xlsx"
    cfg["_workbook"] = (base / cfg.get("workbook", default_wb)).resolve()
    cfg["_output_dir"] = (base / cfg.get("output_dir", "ai-log")).resolve()
    # 圖片統一放在子資料夾（預設 <output_dir>/images）
    cfg["_image_dir"] = (base / cfg.get("image_dir", cfg.get("output_dir", "ai-log") + "/images")).resolve()
    return cfg


# ---------- 去重 ----------
def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def parse_source(date: str, source: str):
    """回傳 (session 前綴, 起始分鐘, 結束分鐘, 日期)；格式不符回傳 None。結束早於起始視為跨日。"""
    m = SOURCE_RE.match(str(source or "").strip())
    if not m:
        return None
    s, e = _minutes(m.group(2)), _minutes(m.group(3))
    if e < s:
        e += 24 * 60
    return m.group(1), s, e, str(date)


def is_duplicate(new: tuple, existing: list[tuple]) -> bool:
    for sid, s, e, d in existing:
        if sid == new[0] and d == new[3] and new[1] < e and s < new[2]:
            return True
    return False


def existing_sources(ws) -> list[tuple]:
    out = []
    for r in range(2, ws.max_row + 1):
        date, src = ws.cell(r, 1).value, ws.cell(r, COL_SOURCE).value
        if src:
            p = parse_source(_date_str(date), src)
            if p:
                out.append(p)
    return out


def _date_str(v) -> str:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    return str(v or "")


# ---------- 活頁簿 ----------
def _new_workbook() -> Workbook:
    wb = Workbook()
    info = wb.active
    info.title = SHEET_INFO
    lines = (TEMPLATE_DIR / "instructions.md").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(l for l in lines if l.strip()):
        c = info.cell(i + 1, 1, line.strip())
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if i == 0:
            c.font = Font(bold=True, size=14)
    info.column_dimensions["A"].width = 110
    log = wb.create_sheet(SHEET_LOG)
    for i, h in enumerate(HEADERS, 1):
        c = log.cell(1, i, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F2937")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        log.column_dimensions[c.column_letter].width = WIDTHS[i - 1]
    log.freeze_panes = "A2"
    wb.create_sheet(SHEET_OPT)
    return wb


def _write_options(ws, cfg: dict):
    ws.delete_rows(1, ws.max_row)
    cols = [("軟工活動", cfg["activities"]), ("採用程度", cfg["adoption_levels"])]
    for ci, (title, items) in enumerate(cols, 1):
        ws.cell(1, ci, title).font = Font(bold=True)
        for ri, it in enumerate(items, 2):
            ws.cell(ri, ci, it)
        ws.column_dimensions[ws.cell(1, ci).column_letter].width = 16
    return {k: len(v) for k, (_, v) in zip("AB", cols)}


def _apply_validations(log, counts: dict):
    log.data_validations.dataValidation = []
    # 紀錄表 B 欄（軟工活動）← 選項 A 欄；H 欄（採用程度）← 選項 B 欄
    spec = {"B": ("A", counts["A"]), "H": ("B", counts["B"])}
    for target, (opt_col, n) in spec.items():
        dv = DataValidation(type="list", formula1=f"'{SHEET_OPT}'!${opt_col}$2:${opt_col}${n + 1}",
                            allow_blank=True, showErrorMessage=True)
        dv.add(f"{target}2:{target}{VALIDATION_ROWS}")
        log.add_data_validation(dv)


def _relative_link(workbook: Path, image: Path) -> str:
    return os.path.relpath(image, workbook.parent).replace("\\", "/")


def _norm_image(i) -> dict:
    """草稿的 images 可以是檔名字串，或 {"file": 檔名, "kind": 類型標籤}。"""
    return i if isinstance(i, dict) else {"file": str(i), "kind": None}


def _image_label(img: dict, wbpath: Path, cfg: dict) -> str:
    rel = _relative_link(wbpath, cfg["_image_dir"] / img["file"])
    return f"[{img['kind']}] {rel}" if img.get("kind") else rel


def validate_rows(rows: list[dict], cfg: dict):
    problems = []
    for i, r in enumerate(rows, 1):
        if r.get("activity") not in cfg["activities"]:
            problems.append(f"第 {i} 列：軟工活動「{r.get('activity')}」不在設定檔選項中")
        if r.get("adoption") not in cfg["adoption_levels"]:
            problems.append(f"第 {i} 列：採用程度「{r.get('adoption')}」不在設定檔選項中")
        if not r.get("judgment"):
            problems.append(f"第 {i} 列：人工判斷與修正不可空白（找不到依據請寫 [待確認] …）")
    return problems


def check_writable(path: Path):
    """Windows 上 Excel 開著檔案時無法寫入；先試一次，不動到內容。"""
    if path.exists():
        try:
            with open(path, "r+b"):
                pass
        except PermissionError as e:
            raise WorkbookLocked(f"請先關閉 Excel 中的 {path.name} 再重試") from e


def append_rows(draft: dict, cfg: dict) -> dict:
    """回傳 {'added': n, 'skipped': [source...], 'pending': [列號...]}。"""
    rows = draft["rows"]
    problems = validate_rows(rows, cfg)
    if problems:
        raise ValueError("草稿有誤：\n" + "\n".join(problems))
    wbpath: Path = cfg["_workbook"]
    check_writable(wbpath)
    wb = load_workbook(wbpath) if wbpath.exists() else _new_workbook()
    log = wb[SHEET_LOG]
    header = [c.value for c in log[1]][:len(HEADERS)]
    if header != HEADERS:
        raise ValueError(f"{wbpath.name} 的欄位和目前版本不同（舊版有「成員」欄），為避免資料錯位未寫入。\n"
                         "請把它改名備份，或在設定檔的 workbook 改用新的檔名後重跑。")
    if SHEET_OPT not in wb.sheetnames:
        wb.create_sheet(SHEET_OPT)
    counts = _write_options(wb[SHEET_OPT], cfg)
    seen = existing_sources(log)
    added, skipped, pending = 0, [], []
    for r in rows:
        parsed = parse_source(r.get("date", ""), r.get("source", ""))
        if parsed and is_duplicate(parsed, seen):
            skipped.append(r.get("source"))
            continue
        if parsed:
            seen.append(parsed)
        row_no = log.max_row + 1
        images = [_norm_image(i) for i in (r.get("images") or [])]
        # 檔案欄是給「讀 Excel 的 AI」看的：每張圖寫出相對路徑與類型，AI 才找得到圖、分得出是誰說的話
        files = [_image_label(i, wbpath, cfg) for i in images] + list(r.get("other_files") or [])
        values = [r.get("date"), r["activity"], r.get("task"), r.get("tool"),
                  r.get("prompt"), r.get("output"), r["judgment"], r["adoption"], "\n".join(files),
                  r.get("section"), r.get("source")]
        for ci, v in enumerate(values, 1):
            c = log.cell(row_no, ci, v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if images:
            c = log.cell(row_no, COL_FILES)
            c.hyperlink = _relative_link(wbpath, cfg["_image_dir"] / images[0]["file"])
            c.font = Font(color="0563C1", underline="single")
        if any(m in str(r["judgment"]) for m in PENDING_MARKS):
            pending.append(row_no)
        added += 1
    _apply_validations(log, counts)
    if added:
        wbpath.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=wbpath.parent)
        os.close(fd)
        try:
            wb.save(tmp)
            os.replace(tmp, wbpath)
        except PermissionError as e:
            raise WorkbookLocked(f"請先關閉 Excel 中的 {wbpath.name} 再重試") from e
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return {"added": added, "skipped": skipped, "pending": pending}


def update_state(cfg: dict, draft: dict, added: int):
    sid = draft.get("session_id")
    if not sid or not added:
        return
    p = cfg["_output_dir"] / STATE_NAME
    state = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"sessions": {}}
    prev = state["sessions"].get(sid, {})
    files = sorted(set(prev.get("files", [])) | set(draft.get("outputs", [])))
    state["sessions"][sid] = {
        "processed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows_added": prev.get("rows_added", 0) + added,
        "files": files,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    cfg = load_config(Path(a.config))
    draft = json.loads(Path(a.draft).read_text(encoding="utf-8-sig"))
    try:
        res = append_rows(draft, cfg)
    except WorkbookLocked as e:
        print(f"無法寫入：{e}\n草稿已保留於 {a.draft}，關閉 Excel 後只要重新執行：\n"
              f"  python write_workbook.py \"{a.draft}\" --config \"{a.config}\"", file=sys.stderr)
        return 2
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    update_state(cfg, draft, res["added"])
    print(f"已寫入 {cfg['_workbook']}：新增 {res['added']} 列")
    if res["skipped"]:
        print("已存在（來源與時間範圍重疊），略過：" + "、".join(map(str, res["skipped"])))
    if res["pending"]:
        print("下列列號的「人工判斷與修正」含 [待確認]／[待補理由]，請補充：" + "、".join(map(str, res["pending"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
