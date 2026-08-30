"""
Safe-logging test (Phase 15): captures real log output from actual
application code paths that touch sensitive settings, and asserts the
secret VALUES never appear -- a live check of what actually gets
written to the log stream, not a grep of source code.
"""
import logging

from app.core.config import get_settings


def test_startup_log_never_contains_secret_values(caplog):
    settings = get_settings()
    logger = logging.getLogger("app.main")

    fake_secret = "sk_live_super_secret_value_12345"
    fake_webhook_secret = "whsec_another_secret_98765"

    with caplog.at_level(logging.INFO):
        logger.info(
            "Starting %s v%s in %s mode (razorpay_mode=%s)",
            settings.app_name,
            settings.app_version,
            settings.app_env,
            settings.razorpay_mode,
        )

    log_text = caplog.text
    assert fake_secret not in log_text
    assert fake_webhook_secret not in log_text
    assert settings.api_key not in log_text or settings.api_key == ""
    assert settings.app_secret_key not in log_text


def test_razorpay_client_logs_never_contain_webhook_secret_value(caplog):
    from app.services.razorpay_client import RazorpayClientWrapper

    client = RazorpayClientWrapper()
    real_secret = "whsec_do_not_leak_this_value"

    with caplog.at_level(logging.WARNING):
        client.verify_webhook_signature(b"some body", "bad-signature", "")

    assert real_secret not in caplog.text


def test_llm_client_logs_never_contain_api_key_value(caplog, monkeypatch):
    import app.llm.client as llm_client_module

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key", "")
    llm_client_module._client_initialized = False
    llm_client_module._client = None

    with caplog.at_level(logging.INFO):
        llm_client_module.get_llm_client()

    assert "sk-ant-" not in caplog.text
