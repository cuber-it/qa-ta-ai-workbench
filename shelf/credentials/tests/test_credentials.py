"""Tests for uc_credentials: file load, env override, redaction, listing."""
import pytest

import uc_credentials as creds

YAML = """\
myapp:
  type: basic
  username: max
  password: s3cret
shop:
  type: form
  url: https://shop.example/login
  username: max@firma.de
  password: hunter2
  user_field: E-Mail
  pass_field: Passwort
  submit: "role=button[name=Login]"
  note: anything extra is kept
"""


@pytest.fixture
def store(tmp_path, monkeypatch):
    # no stray env overrides from the real environment
    for k in list(__import__("os").environ):
        if k.startswith("QATAKI_CRED__"):
            monkeypatch.delenv(k, raising=False)
    p = tmp_path / "credentials.yaml"
    p.write_text(YAML, encoding="utf-8")
    creds.set_store_path(p)
    yield p
    creds.set_store_path(None)


def test_get_basic(store):
    c = creds.get("myapp")
    assert c.type == "basic"
    assert c.username == "max"
    assert c.secret() == "s3cret"


def test_password_is_redacted(store):
    c = creds.get("myapp")
    assert "s3cret" not in repr(c)
    assert "s3cret" not in str(c)
    assert "**" in repr(c.password)
    assert c.secret() == "s3cret"          # real value only via secret()


def test_form_fields_and_extra(store):
    c = creds.get("shop")
    assert c.type == "form"
    assert c.url == "https://shop.example/login"
    assert c.user_field == "E-Mail" and c.pass_field == "Passwort"
    assert c.submit == "role=button[name=Login]"
    assert c.model_extra.get("note") == "anything extra is kept"


def test_env_override_wins(store, monkeypatch):
    monkeypatch.setenv("QATAKI_CRED__SHOP__PASSWORD", "from-env")
    assert creds.get("shop").secret() == "from-env"


def test_env_only_profile(tmp_path, monkeypatch):
    creds.set_store_path(tmp_path / "missing.yaml")   # no file
    monkeypatch.setenv("QATAKI_CRED__CI__USERNAME", "runner")
    monkeypatch.setenv("QATAKI_CRED__CI__PASSWORD", "token")
    c = creds.get("ci")
    assert c.username == "runner" and c.secret() == "token"
    creds.set_store_path(None)


def test_list_profiles(store):
    assert creds.list_profiles() == ["myapp", "shop"]


def test_http_credentials(store):
    assert creds.http_credentials("myapp") == {"username": "max", "password": "s3cret"}


def test_unknown_profile_raises(store):
    with pytest.raises(KeyError):
        creds.get("does_not_exist")
