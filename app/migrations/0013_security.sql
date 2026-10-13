-- 0013: sign-in attempt log for lockout (usernames are recorded as typed, so unknown names are throttled too and existence is not revealed).
CREATE TABLE login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  ts REAL NOT NULL,
  success INTEGER NOT NULL,
  client TEXT
);
CREATE INDEX ix_login_attempts ON login_attempts(username, ts);
