import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
import find_sessions as fs  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.jsonl"


def make_claude_dir(tmp_path, project_cwd):
    root = tmp_path / ".claude" / "projects"
    d = root / "d--encoded-name-不重要"
    d.mkdir(parents=True)
    # 本專案的紀錄：把 fixture 的 cwd 換成指定專案
    text = FIXTURE.read_text(encoding="utf-8").replace(json.dumps("C:\\Users\\demo\\proj")[1:-1], json.dumps(project_cwd)[1:-1])
    (d / "11111111-aaaa.jsonl").write_text(text, encoding="utf-8")
    (d / "11111111-aaaa" / "subagents").mkdir(parents=True)
    # 別的專案
    other = root / "other"
    other.mkdir()
    (other / "22222222-bbbb.jsonl").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    # 壞檔
    (d / "bad.jsonl").write_bytes(b"\xff\xfe\x00bad")
    return root


def test_finds_only_this_project_by_cwd(tmp_path):
    proj = r"D:\課程\軟體工程\demo-project"
    root = make_claude_dir(tmp_path, proj)
    res = fs.find_sessions(proj, root, None)
    assert [r["session_id"] for r in res] == ["11111111-aaaa"]
    r = res[0]
    assert r["human_inputs"] == 3 and r["has_subagents"] and not r["processed"]
    assert r["start"] == "2026-10-30 19:45" and r["end"] == "2026-10-30 20:20"


def test_title_comes_from_ai_title_record_and_is_shown_in_table(tmp_path, capsys):
    proj = r"D:\課程\demo-project"
    root = make_claude_dir(tmp_path, proj)
    jl = next(root.rglob("11111111-aaaa.jsonl"))
    with jl.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "ai-title", "aiTitle": "舊標題", "sessionId": "11111111-aaaa"}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"type": "ai-title", "aiTitle": "範例專案的需求清單", "sessionId": "11111111-aaaa"}, ensure_ascii=False) + "\n")
    assert fs.find_sessions(proj, root, None)[0]["title"] == "範例專案的需求清單"  # 取最後一筆
    fs.main(["--project", proj, "--claude-dir", str(root)])
    assert "範例專案的需求清單" in capsys.readouterr().out


def test_missing_title_falls_back(tmp_path):
    proj = r"D:\課程\demo-project"
    root = make_claude_dir(tmp_path, proj)
    assert fs.find_sessions(proj, root, None)[0]["title"] == "（無標題）"


def test_cwd_matching_is_lenient(tmp_path):
    root = make_claude_dir(tmp_path, r"D:\課程\demo-project")
    for variant in ("d:/課程/demo-project", "D:\\課程\\demo-project\\", "D:\\課程\\DEMO-PROJECT"):
        assert len(fs.find_sessions(variant, root, None)) == 1


def test_subfolder_cwd_counts_but_sibling_does_not(tmp_path):
    root = make_claude_dir(tmp_path, r"D:\課程\demo-project\src")
    assert len(fs.find_sessions(r"D:\課程\demo-project", root, None)) == 1
    assert len(fs.find_sessions(r"D:\課程\demo", root, None)) == 0


def test_processed_flag_and_default_filter(tmp_path, capsys):
    proj = r"D:\課程\demo-project"
    root = make_claude_dir(tmp_path, proj)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"sessions": {"11111111-aaaa": {}}}), encoding="utf-8")
    assert fs.find_sessions(proj, root, state)[0]["processed"] is True
    fs.main(["--project", proj, "--claude-dir", str(root), "--state", str(state), "--json"])
    assert json.loads(capsys.readouterr().out) == []
    fs.main(["--project", proj, "--claude-dir", str(root), "--state", str(state), "--json", "--all"])
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_missing_claude_dir(tmp_path):
    assert fs.find_sessions("x", tmp_path / "nope", None) == []
