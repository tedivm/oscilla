from typing import Any
from unittest.mock import patch

import pytest

from oscilla.services.email import EmailDeliveryError, send_email


@pytest.mark.asyncio
async def test_send_email_no_smtp_host_is_noop(monkeypatch: Any) -> None:
    """When smtp_host is None, send_email completes without error and SMTP is never called."""
    smtp_called = False

    class FakeSMTP:
        def __init__(self, **kwargs: Any) -> None:
            nonlocal smtp_called
            smtp_called = True

        async def __aenter__(self) -> "FakeSMTP":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

    with (
        patch("oscilla.services.email.settings") as mock_settings,
        patch("aiosmtplib.SMTP", FakeSMTP),
    ):
        mock_settings.smtp_host = None
        await send_email(
            to="user@example.com",
            subject="Test",
            body_html="<p>Hello</p>",
            body_text="Hello",
        )

    assert not smtp_called, "aiosmtplib.SMTP should not be instantiated when smtp_host is None"


@pytest.mark.asyncio
async def test_send_email_with_smtp_host_calls_smtp(monkeypatch: Any) -> None:
    """When smtp_host is set, send_email invokes the SMTP client with the correct arguments."""
    smtp_init_kwargs: dict[str, Any] = {}
    sent_message: Any = None

    class FakeSMTP:
        def __init__(self, **kwargs: Any) -> None:
            smtp_init_kwargs.update(kwargs)

        async def __aenter__(self) -> "FakeSMTP":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def send_message(self, msg: Any) -> None:
            nonlocal sent_message
            sent_message = msg

    with (
        patch("oscilla.services.email.settings") as mock_settings,
        patch("aiosmtplib.SMTP", FakeSMTP),
    ):
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 1025
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.smtp_from_address = "oscilla@localhost"

        await send_email(
            to="user@example.com",
            subject="Hello",
            body_html="<p>Hello</p>",
            body_text="Hello",
        )

    assert smtp_init_kwargs["hostname"] == "localhost"
    assert smtp_init_kwargs["port"] == 1025
    assert smtp_init_kwargs["start_tls"] is False
    assert sent_message is not None
    assert sent_message["To"] == "user@example.com"
    assert sent_message["Subject"] == "Hello"


@pytest.mark.asyncio
async def test_send_email_smtp_failure_raises_delivery_error() -> None:
    """When the SMTP client raises an exception, send_email raises EmailDeliveryError."""

    class FailingSMTP:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "FailingSMTP":
            raise ConnectionRefusedError("Cannot connect")

        async def __aexit__(self, *args: Any) -> None:
            pass

    with (
        patch("oscilla.services.email.settings") as mock_settings,
        patch("aiosmtplib.SMTP", FailingSMTP),
    ):
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 1025
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.smtp_from_address = "oscilla@localhost"

        with pytest.raises(EmailDeliveryError):
            await send_email(
                to="user@example.com",
                subject="Test",
                body_html="<p>Hello</p>",
                body_text="Hello",
            )


@pytest.mark.asyncio
async def test_send_email_authenticates_when_smtp_user_configured() -> None:
    """When smtp_user is configured, send_email passes username and password to SMTP."""
    smtp_init_kwargs: dict[str, Any] = {}

    class FakeSMTP:
        def __init__(self, **kwargs: Any) -> None:
            smtp_init_kwargs.update(kwargs)

        async def __aenter__(self) -> "FakeSMTP":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def send_message(self, msg: Any) -> None:
            pass

    class FakeSecretStr:
        def get_secret_value(self) -> str:
            return "secret-password"

    with (
        patch("oscilla.services.email.settings") as mock_settings,
        patch("aiosmtplib.SMTP", FakeSMTP),
    ):
        mock_settings.smtp_host = "localhost"
        mock_settings.smtp_port = 587
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_user = "testuser"
        mock_settings.smtp_password = FakeSecretStr()
        mock_settings.smtp_from_address = "oscilla@localhost"

        await send_email(
            to="user@example.com",
            subject="Test Auth",
            body_html="<p>Hello</p>",
            body_text="Hello",
        )

    assert smtp_init_kwargs.get("username") == "testuser"
    assert smtp_init_kwargs.get("password") == "secret-password"
