"""Sign-in: accounts with email and password, browser sessions and API keys, all in PostgreSQL.

The visor signs in with `POST /api/auth/login` and then holds an HttpOnly session cookie; scripts
send an API key as `Authorization: Bearer <key>` (`api-keys create` in the CLI). A route requires
a signed-in caller with a `CurrentUser` (or `AdminUser`) parameter from `deps.py`.

Invariants (tests/test_auth.py checks each one):

- The session token travels only in the cookie, never in a JSON body.
- Sessions and API keys are stored as the SHA-256 of their secret, never the secret itself.
- No GET request changes state; a state-changing request authenticated by the cookie must come
  from the visor's own origin (`deps.check_same_origin`, against cross-site request forgery).
- A wrong password and an unknown email get the same answer, after the same work.
- Logout deletes the session; a new password or a deactivated account ends the user's sessions.
"""
