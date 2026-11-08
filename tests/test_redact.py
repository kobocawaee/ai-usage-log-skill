import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-usage-log" / "scripts"))
from redact import redact  # noqa: E402


def r(s):
    return redact(s)[0]


def test_prefixed_keys():
    assert r("key sk-abcdEFGH12345678xyz ok") == "key [已遮罩] ok"
    assert r("ghp_" + "a1" * 12) == "[已遮罩]"
    assert r("gho_abcdefgh12345678") == "[已遮罩]"
    assert r("xoxb-1234567890-abcdefghij") == "[已遮罩]"
    assert r("xoxp-1234567890-abcdefghij") == "[已遮罩]"


def test_long_token_needs_letters_and_digits():
    tok = "A1b2C3d4" * 5  # 40 字元
    assert r(f"token={tok}!") == "token=[已遮罩]!"
    assert r("x" * 40) == "x" * 40  # 純字母不遮罩
    assert r("test_user_registration_with_invalid_email_address") == "test_user_registration_with_invalid_email_address"
    assert r("a1" * 15) == "a1" * 15  # 30 字元，未達 32
    assert r("a1" * 16) == "[已遮罩]"


def test_uuid_kept():
    u = "12345678-1234-4abc-8def-123456789abc"
    assert r(f"session {u}") == f"session {u}"


def test_email():
    assert r("寄給 foo.bar+x@example.co.uk 謝謝") == "寄給 [email] 謝謝"


def test_home_dirs():
    assert r(r"C:\Users\王小明\proj\a.py") == r"~\proj\a.py"
    assert r("c:/Users/bob/x") == "~/x"
    assert r("/home/alice/code") == "~/code"
    assert r("/Users/carol/code") == "~/code"
    assert r("see /usr/home/x and docs/Users/guide") == "see /usr/home/x and docs/Users/guide"


def test_password_fields():
    assert r("password=hunter2 end") == "password=[已遮罩] end"
    assert r("PASSWORD: s3cret!") == "password=[已遮罩]"
    assert r('pwd: "x y"') == "password=[已遮罩]"
    assert "hunter2" not in r("Password：hunter2")


def test_changed_flag_and_plain_text():
    assert redact("普通文字 1、3 照預設 2. 改成 B") == ("普通文字 1、3 照預設 2. 改成 B", False)
    assert redact("a@b.com")[1] is True
