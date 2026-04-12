# Auth Flows

## Purpose

Specifies all authentication-related pages: landing, about, login, registration, email verification, forgotten password, and password reset. These are the only pages accessible to unauthenticated users. Each page follows the three-state async pattern (loading / error / data) defined in design D8.

---

## Requirements

### Requirement: Landing page (`/app`)

The landing page SHALL be public. It SHALL describe the Oscilla platform with a call-to-action button leading to `/app/login`. If the user is already authenticated, `onMount` SHALL redirect to `/app/games`.

#### Scenario: Authenticated user is redirected

- **GIVEN** `$isLoggedIn === true`
- **WHEN** the user navigates to `/app`
- **THEN** the user is redirected to `/app/games`.

---

### Requirement: About page (`/app/about`)

The about page SHALL be public and render static informational content. No auth guard needed.

---

### Requirement: Login page (`/app/login`)

The login page SHALL:

- Render a form with an email field and a password field, both with associated `<label>` elements.
- On submission call `api.login(email, password)` (with `skipAuth=true`). On success: call `authStore.login(pair, user)` and redirect to the `?next=` URL (default: `/app/games`).
- On failure display a field-level or form-level error message linked via `aria-describedby`.
- Redirect to `/app/games` on `onMount` if already authenticated.

#### Scenario: Valid credentials log in and redirect

- **GIVEN** the server accepts the credentials
- **WHEN** the user submits the login form
- **THEN** `authStore.login()` is called with the returned `TokenPair` and `UserRead`
- **AND** the user is navigated to `/app/games` (or `?next=` if provided).

#### Scenario: Invalid credentials show an error

- **GIVEN** the server returns 401 on the login attempt
- **WHEN** the user submits the form
- **THEN** an error message is displayed in the form
- **AND** the user remains on the login page.

#### Scenario: Form fields have accessible labels

- **GIVEN** the login page is rendered
- **THEN** both the email `<input>` and the password `<input>` each have an associated `<label>` (via `for`/`id` pairing).

---

### Requirement: Registration page (`/app/register`)

The registration page SHALL:

- Render a form with email, password, and confirm-password fields with associated `<label>` elements.
- Validate that password and confirm-password match before submitting.
- On submission call `authStore.register(email, password)`.
- On `201 Created`: show a confirmation message prompting the user to verify email and include a link to `/app/login`.
- On `409 Conflict`: display "An account with this email already exists."
- On `422`: render per-field validation errors linked via `aria-describedby`.
- Redirect to `/app/games` on `onMount` if already authenticated.

#### Scenario: Successful registration shows verification prompt

- **GIVEN** the server creates the account
- **WHEN** the user submits the registration form
- **THEN** a confirmation message is shown indicating email verification is required
- **AND** a login link is rendered.

#### Scenario: Duplicate email shows conflict error

- **GIVEN** the server returns 409
- **WHEN** the user submits the registration form
- **THEN** the message "An account with this email already exists." is visible in the form.

---

### Requirement: Email verification landing (`/app/verify`)

The verification page SHALL:

- Read the `?token=` URL query parameter.
- If no token is present, render a prompt to request a new verification email.
- If a token is present, call `GET /auth/verify/{token}` on mount and display success or failure feedback.
- On success, show a link to log in.

#### Scenario: Valid token shows success message

- **GIVEN** the URL contains a valid `?token=`
- **WHEN** the page mounts
- **THEN** `GET /auth/verify/{token}` is called
- **AND** a success message is rendered.

#### Scenario: Invalid or expired token shows error

- **GIVEN** the URL contains an expired or invalid `?token=`
- **WHEN** the page mounts
- **THEN** an error message is rendered with a prompt to request a new verification email.

---

### Requirement: Forgot password page (`/app/forgot-password`)

The forgot-password page SHALL:

- Render a form with a single email field and associated `<label>`.
- On submission call `api.requestPasswordReset(email)`.
- Always show a success-style message regardless of whether the email exists (to prevent email enumeration).

#### Scenario: Email enumeration is prevented

- **GIVEN** any email address (registered or not)
- **WHEN** the user submits the forgot-password form
- **THEN** the same "If an account exists for this email, a reset link has been sent." message is displayed.

---

### Requirement: Password reset page (`/app/reset-password`)

The password reset page SHALL:

- Read the `?token=` URL query parameter.
- Render a form with a new password field and associated `<label>`.
- On submission call `api.resetPassword(token, newPassword)`.
- On success display a confirmation message and a link to log in.
- On `400`/`422` (invalid or expired token) display a message prompting the user to request a new reset link.
