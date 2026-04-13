# Password Strength

## Purpose

Specifies the password strength validation added to the user registration and password reset endpoints. The [zxcvbn](https://github.com/dwolfhub/zxcvbn-python) library is used to score passwords on a scale of 0–4. Passwords scoring below the configured threshold are rejected at the API boundary with a 422 response that includes a human-readable suggestion from zxcvbn.

---

## Requirements

### Requirement: Registration rejects weak passwords with a suggestion

`POST /auth/register` SHALL call `zxcvbn(password)` on the plain-text password value from the `UserCreate` request body. If the resulting score is less than `settings.min_password_strength` (default `2`), the endpoint SHALL raise `HTTPException(status_code=422)` with a detail string that includes the first suggestion from `zxcvbn_result["feedback"]["suggestions"]`, or a generic fallback message if no suggestions are available.

The zxcvbn check SHALL be performed before the password is hashed and before any database write. This ensures no partial side effects occur for rejected passwords.

#### Scenario: weak password rejected at registration with suggestion

- **GIVEN** `min_password_strength = 2`
- **WHEN** `POST /auth/register` is called with a password whose zxcvbn score is `0` (e.g., `"password"`)
- **THEN** the response status is `422`
- **AND** the response body contains a human-readable suggestion string

#### Scenario: strong password accepted at registration

- **GIVEN** `min_password_strength = 2`
- **WHEN** `POST /auth/register` is called with a password whose zxcvbn score is `>= 2` (e.g., a 16-character random string)
- **THEN** the response status is `201` and the user is created

#### Scenario: fallback message when zxcvbn has no suggestions

- **GIVEN** a password that scores below the threshold with no suggestions in the feedback
- **WHEN** `POST /auth/register` is called
- **THEN** the response status is `422`
- **AND** the detail contains a generic fallback message (not an empty string)

---

### Requirement: Password reset rejects weak passwords with a suggestion

`POST /auth/reset-password` (the endpoint that consumes a reset token and sets a new password) SHALL apply the same zxcvbn check. If the new password scores below `settings.min_password_strength`, the endpoint SHALL return `422` with the same suggestion format as registration.

#### Scenario: weak new password rejected at reset

- **GIVEN** a valid password reset token and `min_password_strength = 2`
- **WHEN** `POST /auth/reset-password` is called with a password scoring `0`
- **THEN** the response status is `422`
- **AND** the reset token is NOT consumed (it remains valid for a subsequent attempt)

#### Scenario: strong new password accepted at reset

- **GIVEN** a valid password reset token and `min_password_strength = 2`
- **WHEN** `POST /auth/reset-password` is called with a sufficiently strong password
- **THEN** the response status is `200` and the password is updated

---

### Requirement: min_password_strength is a configurable setting

`oscilla/conf/settings.py` SHALL add:

```python
min_password_strength: int = Field(
    default=2,
    description="Minimum zxcvbn password score (0-4) required for registration and password reset.",
)
```

A value of `0` disables strength enforcement (all passwords accepted). The valid range is `0–4`.

#### Scenario: strength enforcement disabled when min_password_strength is 0

- **GIVEN** `min_password_strength = 0`
- **WHEN** `POST /auth/register` is called with `"password"` (zxcvbn score 0)
- **THEN** the response status is `201` and the user is created
