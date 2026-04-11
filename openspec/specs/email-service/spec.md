# Email Service

## Purpose

Specifies `oscilla/services/email.py` — a standalone async email dispatcher used by the auth service and available to any future feature. The service is deliberately independent of auth logic: it accepts recipients, subjects, and pre-rendered body content, then dispatches via SMTP using `aiosmtplib`.

---

## Requirements

### Requirement: send_email is a graceful no-op when smtp_host is not configured

When `settings.smtp_host` is `None`, `send_email` SHALL:

1. Log a DEBUG message explaining that SMTP is not configured.
2. Return immediately without making any network connection.
3. NOT raise any exception.

This enables development and test environments that have no SMTP server to register users, trigger password resets, and run auth flows without errors.

#### Scenario: send_email with smtp_host=None returns without error

- **GIVEN** `settings.smtp_host = None`
- **WHEN** `await send_email(to="user@example.com", subject="Test", body_html="<p>Hi</p>", body_text="Hi")` is called
- **THEN** the coroutine completes without raising any exception
- **AND** no `aiosmtplib.SMTP` instance is created

---

### Requirement: send_email dispatches a dual-format MIME message when SMTP is configured

When `settings.smtp_host` is set, `send_email(to, subject, body_html, body_text)` SHALL:

1. Construct a `email.mime.multipart.MIMEMultipart("alternative")` message.
2. Attach a `text/plain` part with `body_text`.
3. Attach a `text/html` part with `body_html`.
4. Set `From` to `settings.smtp_from_address`, `To` to the `to` argument, and `Subject` to `subject`.
5. Open an `aiosmtplib.SMTP` connection with `hostname=settings.smtp_host`, `port=settings.smtp_port`, and `start_tls=settings.smtp_use_tls`.
6. If `settings.smtp_user` is set, authenticate using `smtp_user` and `settings.smtp_password.get_secret_value()`.
7. Send the message and close the connection.
8. Return `None` on success.

#### Scenario: send_email constructs a MIMEMultipart message with both parts

- **GIVEN** `settings.smtp_host = "localhost"` and monkeypatched `aiosmtplib.SMTP`
- **WHEN** `await send_email(to="r@example.com", subject="Hello", body_html="<b>Hi</b>", body_text="Hi")` is called
- **THEN** `aiosmtplib.SMTP` is instantiated with the configured host and port
- **AND** `send_message` is called with a `MIMEMultipart` message containing a `text/plain` part and a `text/html` part

#### Scenario: send_email authenticates when smtp_user is configured

- **GIVEN** `settings.smtp_host = "mail.example.com"`, `settings.smtp_user = "sender"`, `settings.smtp_password = SecretStr("secret")`, and monkeypatched `aiosmtplib.SMTP`
- **WHEN** `await send_email(...)` is called
- **THEN** the SMTP client's `login` method is called with `"sender"` and `"secret"`

#### Scenario: send_email skips authentication when smtp_user is None

- **GIVEN** `settings.smtp_user = None` and monkeypatched `aiosmtplib.SMTP`
- **WHEN** `await send_email(...)` is called
- **THEN** the SMTP client's `login` method is NOT called

---

### Requirement: SMTP failures raise EmailDeliveryError

When the SMTP operation raises any exception, `send_email` SHALL catch it, log it using `logger.exception`, and raise `EmailDeliveryError`.

`EmailDeliveryError` is defined in `oscilla/services/email.py` as a plain exception subclass:

```python
class EmailDeliveryError(Exception):
    """Raised when the SMTP delivery operation fails."""
```

Callers are responsible for deciding whether `EmailDeliveryError` should be propagated or suppressed. The auth service suppresses it (logs and continues) for registration and resend-verify flows so that an SMTP outage does not block account creation. It propagates from password-reset only if the link cannot be sent — the design leaves this to the caller's discretion.

#### Scenario: SMTP connection failure raises EmailDeliveryError

- **GIVEN** monkeypatched `aiosmtplib.SMTP` that raises `aiosmtplib.SMTPException` on connect
- **WHEN** `await send_email(...)` is called
- **THEN** `EmailDeliveryError` is raised
- **AND** `logger.exception` has been called

#### Scenario: SMTP send failure raises EmailDeliveryError

- **GIVEN** monkeypatched `aiosmtplib.SMTP` that raises `aiosmtplib.SMTPException` on `send_message`
- **WHEN** `await send_email(...)` is called
- **THEN** `EmailDeliveryError` is raised

---

### Requirement: Email service has no dependency on auth logic

`oscilla/services/email.py` MUST NOT import from `oscilla/services/auth.py` or any auth-model module. Its only external runtime dependencies are `aiosmtplib`, Python stdlib `email` and `logging` modules, and `oscilla.settings`. This ensures future features can send email without coupling to the auth service.

#### Scenario: email.py has no direct import from services.auth

- **GIVEN** the source text of `oscilla/services/email.py`
- **THEN** it contains no `import` statement referencing `oscilla.services.auth` or `oscilla.models.auth`
