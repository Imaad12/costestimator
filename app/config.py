"""Configuration: defaults from config/settings.toml, overridden by .env and KSA_* environment variables."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    return out


def _truthy(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    db_path: Path = BASE_DIR / "var" / "ksa_estimator.db"
    data_dir: Path = BASE_DIR / "data"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str | None = None
    allow_self_approval: bool = True
    token_ttl_hours: int = 12
    csrf_origin_check: bool = True              # cookie-authenticated unsafe requests must come from the same origin
    security_headers: bool = True
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    tls: bool = False                           # set when the app is served over TLS (cookies Secure, HSTS)
    ai_enabled: bool = False
    ai_model: str = "claude-sonnet-5-5"
    ai_max_tokens: int = 2000
    anthropic_api_key: str | None = None
    workspaces_override: Path | None = None
    company: dict = field(default_factory=dict)
    approval_thresholds: dict = field(default_factory=dict)
    reconciliation: dict = field(default_factory=dict)

    # ---- derived paths -------------------------------------------------
    @property
    def var_dir(self) -> Path:
        return self.db_path.parent

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def workspaces_dir(self) -> Path:
        """Numbered per-project workspaces (docs/PROJECT_WORKSPACES.md). Default: <repo>/projects."""
        return self.workspaces_override or (self.base_dir / "projects")

    @property
    def imports_dir(self) -> Path:
        """Original public-source files + import manifests (never overwritten); runtime data, included in backups."""
        return self.var_dir / "imports"

    @property
    def source_cache_dir(self) -> Path:
        return self.var_dir / "source_cache"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def backups_dir(self) -> Path:
        return self.var_dir / "backups"

    def ensure_dirs(self) -> None:
        for p in (self.var_dir, self.projects_dir, self.outputs_dir, self.backups_dir, self.workspaces_dir):
            p.mkdir(parents=True, exist_ok=True)

    def get_secret(self) -> str:
        if self.secret_key:
            return self.secret_key
        key_file = self.var_dir / "secret.key"
        self.var_dir.mkdir(parents=True, exist_ok=True)
        if not key_file.exists():
            import secrets

            key_file.write_text(secrets.token_hex(32))
            try:
                key_file.chmod(0o600)
            except OSError:
                pass
        return key_file.read_text().strip()


def _abs(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else BASE_DIR / p


def load_settings(config_file: Path | None = None, env: dict | None = None) -> Settings:
    cfg_path = config_file or (BASE_DIR / "config" / "settings.toml")
    raw: dict = {}
    if cfg_path.exists():
        raw = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    environ = {**_load_dotenv(BASE_DIR / ".env"), **(env if env is not None else os.environ)}
    app, sec, ai = raw.get("app", {}), raw.get("security", {}), raw.get("ai", {})

    def pick(env_key: str, default):
        return environ.get(env_key, default)

    s = Settings(
        db_path=_abs(pick("KSA_DB_PATH", app.get("db_path", "var/ksa_estimator.db"))),
        data_dir=_abs(pick("KSA_DATA_DIR", app.get("data_dir", "data"))),
        workspaces_override=(_abs(pick("KSA_WORKSPACES_DIR", app.get("workspaces_dir", ""))) if pick("KSA_WORKSPACES_DIR", app.get("workspaces_dir", "")) else None),
        log_level=str(pick("KSA_LOG_LEVEL", app.get("log_level", "INFO"))),
        host=str(pick("KSA_HOST", app.get("host", "127.0.0.1"))),
        port=int(pick("KSA_PORT", app.get("port", 8000))),
        secret_key=environ.get("KSA_SECRET_KEY") or None,
        allow_self_approval=_truthy(pick("KSA_ALLOW_SELF_APPROVAL", sec.get("allow_self_approval", True))),
        token_ttl_hours=int(pick("KSA_TOKEN_TTL_HOURS", sec.get("token_ttl_hours", 12))),
        csrf_origin_check=_truthy(pick("KSA_CSRF_ORIGIN_CHECK", sec.get("csrf_origin_check", True))),
        security_headers=_truthy(pick("KSA_SECURITY_HEADERS", sec.get("security_headers", True))),
        login_max_failures=int(pick("KSA_LOGIN_MAX_FAILURES", sec.get("login_max_failures", 5))),
        login_lock_minutes=int(pick("KSA_LOGIN_LOCK_MINUTES", sec.get("login_lock_minutes", 15))),
        tls=_truthy(pick("KSA_TLS", sec.get("tls", False))),
        ai_enabled=_truthy(pick("KSA_AI_ENABLED", ai.get("enabled", False))),
        ai_model=str(pick("KSA_AI_MODEL", ai.get("model", "claude-sonnet-5-5"))),
        ai_max_tokens=int(pick("KSA_AI_MAX_TOKENS", ai.get("max_tokens", 2000))),
        anthropic_api_key=environ.get("ANTHROPIC_API_KEY") or None,
        company=dict(raw.get("company", {})),
        approval_thresholds=dict(raw.get("approval_thresholds", {})),
        reconciliation=dict(raw.get("reconciliation", {})),
    )
    return s


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def set_settings(s: Settings | None) -> None:
    """Override (tests) or reset (None) the process-wide settings."""
    global _settings
    _settings = s
