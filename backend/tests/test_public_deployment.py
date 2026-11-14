"""Public demo must never silently expose the hardcoded local admin password."""

import pytest

from app.seed import demo_accounts


def test_local_development_defaults_remain_available(monkeypatch):
    monkeypatch.delenv("PUBLIC_DEMO_MODE", raising=False)
    accounts = demo_accounts()
    assert accounts[0][1:] == ("admin@snackoverflow.dev", "Admin123!", "admin")
    assert accounts[1][1:] == ("member@snackoverflow.dev", "Member123!", "member")


def test_public_deployment_requires_private_credentials(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    for key in ("DEMO_ADMIN_EMAIL", "DEMO_ADMIN_PASSWORD", "DEMO_MEMBER_EMAIL", "DEMO_MEMBER_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="Public demo requires"):
        demo_accounts()


def test_public_deployment_uses_strong_nondefault_credentials(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "review-admin@example.com")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "strong-review-admin-password")
    monkeypatch.setenv("DEMO_MEMBER_EMAIL", "review-member@example.com")
    monkeypatch.setenv("DEMO_MEMBER_PASSWORD", "strong-review-member-password")
    result = demo_accounts()
    assert result[0][1:] == ("review-admin@example.com", "strong-review-admin-password", "admin")
    assert result[1][1:] == ("review-member@example.com", "strong-review-member-password", "member")


def test_public_deployment_rejects_default_admin_password(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "review-admin@example.com")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("DEMO_MEMBER_EMAIL", "review-member@example.com")
    monkeypatch.setenv("DEMO_MEMBER_PASSWORD", "strong-review-member-password")
    with pytest.raises(RuntimeError, match="DEMO_ADMIN_PASSWORD"):
        demo_accounts()
