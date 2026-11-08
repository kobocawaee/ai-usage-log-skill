import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import write_workbook as ww  # noqa: E402

CONFIG = {
    "member": "成員1", "members": ["成員1"], "output_dir": "ai-log", "workbook": "ai-log/x.xlsx",
    "activities": ["需求"], "adoption_levels": ["直接採用"],
}


def test_image_kind_and_relative_path_written_for_ai_readers(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
    c = ww.load_config(p)
    r = {"date": "2026-10-30", "activity": "需求", "judgment": "x", "adoption": "直接採用",
         "source": "abcd1234 10:00–10:30",
         "images": [{"file": "a_01.png", "kind": "人工決策"}, {"file": "a_02.png", "kind": "AI 產出"}, "a_03.png"]}
    ww.append_rows({"rows": [r]}, c)
    ws = load_workbook(c["_workbook"])["紀錄表"]
    assert ws["J2"].value.split("\n") == ["[人工決策] images/a_01.png", "[AI 產出] images/a_02.png", "images/a_03.png"]
    assert ws["J2"].hyperlink.target == "images/a_01.png"
