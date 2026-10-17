# ScamShield administrative authentication

- Administrative Flask routes must use `@admin_required`.
- The admin token is read only from the server environment variable
  `SCAMSHIELD_ADMIN_TOKEN`.
- Tokens shorter than 32 characters are rejected.
- Missing server configuration fails closed with HTTP 503.
- Missing or invalid credentials receive HTTP 401.
- Never put the admin token in `index.html`, `script.js`, browser storage,
  URLs, source control, screenshots, or API responses.
- Send the token only in the `Authorization: Bearer ...` request header.
- Use HTTPS outside local development.
- Do not create an administrative route without applying authentication
  and reviewing its authorization, input validation, audit logging, and
  failure behavior.
- This token decorator authenticates a shared administrator credential;
  it does not provide individual accounts, role separation, MFA, or
  CSRF protection for cookie-based sessions.
- No security implementation guarantees the absence of all vulnerabilities.
