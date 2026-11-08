import json
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import write_workbook as ww  # noqa: E402

CONFIG = {
    "member": "成員1", "member_name": "王小明", "members": ["成員1", "成員2"], "timezone": "Asia/Taipei",
    "output_dir": "ai-log", "workbook": "ai-log/G-AI使用紀錄-成員1.xlsx",
    "activities": ["需求", "設計", "程式"], "adoption_levels": ["直接採用", "小幅修改", "不採用"],
}


def row(source="abcd1234 19:45–20:19", date="2026-10-30", **kw):
    r = {"date": date, "activity": "需求", "task": "寫範例", "tool": "Claude Code＋demo", "prompt": "「寫範例」",
         "output": "一份範例", "judgment": "我要求新規則從 R10 起編號，因為測試要對應規則編號。",
         "adoption": "小幅修改", "images": ["1030_範例_王小明_01.png"], "other_files": ["docs/prd.md"],
         "section": "B（需求）", "source": source}
    r.update(kw)
    return r


@pytest.fixture
def cfg(tmp_path):
    proj = tmp_path / "課程 專案"
    proj.mkdir()
    p = proj / "ai-usage-log.config.json"
    p.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
    return ww.load_config(p), p


def test_create_new_workbook_structure(cfg):
    c, _ = cfg
    res = ww.append_rows({"session_id": "s", "rows": [row()]}, c)
    assert res["added"] == 1
    wb = load_workbook(c["_workbook"])
    assert wb.sheetnames == ["說明", "紀錄表", "選項"]
    ws = wb["紀錄表"]
    assert [x.value for x in ws[1]] == ww.HEADERS
    assert ws.freeze_panes == "A2"
    assert ws["H2"].alignment.wrap_text
    assert ws["B2"].value == "成員1" and ws["L2"].value == "abcd1234 19:45–20:19"
    assert ws["J2"].value == "images/1030_範例_王小明_01.png\ndocs/prd.md"
    assert ws["J2"].hyperlink.target == "images/1030_範例_王小明_01.png"  # 圖片在子資料夾 → 相對路徑
    opt = wb["選項"]
    assert [opt.cell(i, 1).value for i in (1, 2, 3, 4)] == ["軟工活動", "需求", "設計", "程式"]
    assert opt["C3"].value == "成員2"
    assert wb["說明"].max_row >= 8


def test_dropdowns_reference_options_sheet(cfg):
    c, _ = cfg
    ww.append_rows({"rows": [row()]}, c)
    dvs = {tuple(str(r) for r in dv.sqref.ranges): dv.formula1 for dv in load_workbook(c["_workbook"])["紀錄表"].data_validations.dataValidation}
    assert dvs[("B2:B1000",)] == "'選項'!$C$2:$C$3"
    assert dvs[("C2:C1000",)] == "'選項'!$A$2:$A$4"
    assert dvs[("I2:I1000",)] == "'選項'!$B$2:$B$4"


def test_append_keeps_existing_rows_and_dropdowns(cfg):
    c, _ = cfg
    ww.append_rows({"rows": [row()]}, c)
    res = ww.append_rows({"rows": [row(source="aaaaaaaa 10:00–10:30", task="第二筆")]}, c)
    assert res["added"] == 1
    ws = load_workbook(c["_workbook"])["紀錄表"]
    assert ws.max_row == 3 and ws["D2"].value == "寫範例" and ws["D3"].value == "第二筆"
    assert len(ws.data_validations.dataValidation) == 3


def test_dedupe_by_source_overlap(cfg):
    c, _ = cfg
    ww.append_rows({"rows": [row()]}, c)
    # 同 session、時間重疊 → 略過
    r = ww.append_rows({"rows": [row(source="abcd1234 20:00–20:40")]}, c)
    assert r["added"] == 0 and r["skipped"] == ["abcd1234 20:00–20:40"]
    # 同 session、不重疊 → 新增
    assert ww.append_rows({"rows": [row(source="abcd1234 20:20–21:00")]}, c)["added"] == 1
    # 不同 session 同時間 → 新增
    assert ww.append_rows({"rows": [row(source="deadbeef 19:45–20:19")]}, c)["added"] == 1
    # 同 session 同時間但不同日期 → 新增
    assert ww.append_rows({"rows": [row(date="2026-11-01")]}, c)["added"] == 1
    assert load_workbook(c["_workbook"])["紀錄表"].max_row == 5


def test_dedupe_within_same_draft(cfg):
    c, _ = cfg
    res = ww.append_rows({"rows": [row(), row(source="abcd1234 19:50–20:00")]}, c)
    assert res["added"] == 1 and len(res["skipped"]) == 1


def test_cross_midnight_range():
    a = ww.parse_source("2026-10-30", "x 23:30–00:30")
    assert a[2] - a[1] == 60


def test_validation_rejects_bad_values_and_writes_nothing(cfg):
    c, _ = cfg
    with pytest.raises(ValueError) as e:
        ww.append_rows({"rows": [row(activity="亂寫"), row(adoption="？", judgment="")]}, c)
    assert "亂寫" in str(e.value) and "不可空白" in str(e.value)
    assert not c["_workbook"].exists()


def test_pending_rows_reported(cfg):
    c, _ = cfg
    res = ww.append_rows({"rows": [row(), row(source="aaaaaaaa 10:00–10:30", judgment="[待確認] AI 推測：改了命名")]}, c)
    assert res["pending"] == [3]


def test_state_file_updated(cfg):
    c, _ = cfg
    d = {"session_id": "abcd1234-x", "outputs": ["ai-log/a.png"], "rows": [row()]}
    ww.update_state(c, d, ww.append_rows(d, c)["added"])
    st = json.loads((c["_output_dir"] / ww.STATE_NAME).read_text(encoding="utf-8"))
    assert st["sessions"]["abcd1234-x"]["rows_added"] == 1
    assert st["sessions"]["abcd1234-x"]["files"] == ["ai-log/a.png"]


def test_locked_workbook_reports_and_keeps_draft(cfg, tmp_path, monkeypatch, capsys):
    c, cfgpath = cfg
    ww.append_rows({"rows": [row()]}, c)
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"rows": [row(source="aaaaaaaa 10:00–10:30")]}, ensure_ascii=False), encoding="utf-8")
    real_open = open

    def locked(path, *a, **k):
        if str(path).endswith(".xlsx") and "r+b" in a:
            raise PermissionError(13, "locked")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", locked)
    code = ww.main([str(draft), "--config", str(cfgpath)])
    monkeypatch.undo()
    assert code == 2 and draft.exists()
    err = capsys.readouterr().err
    assert "請先關閉 Excel 中的 G-AI使用紀錄-成員1.xlsx 再重試" in err
    assert load_workbook(c["_workbook"])["紀錄表"].max_row == 2  # 沒有被改動
    assert ww.main([str(draft), "--config", str(cfgpath)]) == 0  # 關檔後只重跑這一步
    assert load_workbook(c["_workbook"])["紀錄表"].max_row == 3


def test_adjacent_ranges_sharing_boundary_are_not_duplicates(cfg):
    c, _ = cfg
    res = ww.append_rows({"rows": [row(source="abcd1234 19:45–20:19"), row(source="abcd1234 20:19–20:40")]}, c)
    assert res["added"] == 2 and res["skipped"] == []


def test_images_live_in_subfolder_and_link_is_relative(cfg):
    c, _ = cfg
    assert c["_image_dir"] == (c["_base"] / "ai-log" / "images").resolve()  # 預設 <output_dir>/images
    ww.append_rows({"rows": [row()]}, c)
    ws = load_workbook(c["_workbook"])["紀錄表"]
    assert ws["J2"].hyperlink.target == "images/1030_範例_王小明_01.png"


def test_custom_image_dir(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({**CONFIG, "image_dir": "pics/cards"}, ensure_ascii=False), encoding="utf-8")
    c = ww.load_config(p)
    ww.append_rows({"rows": [row()]}, c)
    assert load_workbook(c["_workbook"])["紀錄表"]["J2"].hyperlink.target == "../pics/cards/1030_範例_王小明_01.png"
