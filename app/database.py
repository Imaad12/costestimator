"""SQLite access layer: connections, migrations, and small query helpers.

Decimals are stored as TEXT (exact); use app.core.money.D() when reading.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import Settings, get_settings
from .core.timeutil import now_iso

log = logging.getLogger("ksa.db")
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL" if self.path != ":memory:" else "PRAGMA journal_mode = MEMORY")
        self._depth = 0

    # -- transactions ---------------------------------------------------
    @contextmanager
    def tx(self) -> Iterator["Database"]:
        """Nested-safe transaction (savepoints)."""
        name = f"sp{self._depth}"
        if self._depth == 0:
            self.conn.execute("BEGIN")
        else:
            self.conn.execute(f"SAVEPOINT {name}")
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("ROLLBACK")
            else:
                self.conn.execute(f"ROLLBACK TO {name}")
                self.conn.execute(f"RELEASE {name}")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute(f"RELEASE {name}")

    # -- helpers --------------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, tuple(params))

    def insert(self, table: str, values: dict) -> int:
        cols = list(values.keys())
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        cur = self.conn.execute(sql, [_adapt(values[c]) for c in cols])
        return cur.lastrowid

    def update(self, table: str, values: dict, where: str, params: Iterable[Any] = ()) -> int:
        sets = ",".join(f"{c}=?" for c in values)
        sql = f"UPDATE {table} SET {sets} WHERE {where}"
        cur = self.conn.execute(sql, [_adapt(v) for v in values.values()] + list(params))
        return cur.rowcount

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        r = self.conn.execute(sql, tuple(params)).fetchone()
        return None if r is None else r[0]

    def close(self) -> None:
        self.conn.close()

    # -- migrations -----------------------------------------------------
    def migrate(self) -> list[str]:
        """Apply pending SQL migrations in filename order. Returns versions applied."""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {r["version"] for r in self.all("SELECT version FROM schema_migrations")}
        applied: list[str] = []
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if f.stem in done:
                continue
            log.info("applying migration %s", f.stem)
            self.conn.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") + "\nCOMMIT;")
            self.conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?,?)", (f.stem, now_iso())
            )
            applied.append(f.stem)
        return applied


def _adapt(v: Any) -> Any:
    from decimal import Decimal

    from .core.money import to_text

    if isinstance(v, Decimal):
        return to_text(v)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    if hasattr(v, "value") and not isinstance(v, (str, int, float)):  # Enum
        return v.value
    return v


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return None if row is None else {k: row[k] for k in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [{k: r[k] for k in r.keys()} for r in rows]


def jload(text: str | None, default: Any = None) -> Any:
    if text in (None, ""):
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


_db: Database | None = None


def get_db(settings: Settings | None = None) -> Database:
    """Process-wide database (created and migrated on first use)."""
    global _db
    if _db is None:
        s = settings or get_settings()
        s.ensure_dirs()
        _db = Database(s.db_path)
        _db.migrate()
    return _db


def set_db(db: Database | None) -> None:
    global _db
    if _db is not None and db is not _db:
        try:
            _db.close()
        except Exception:
            pass
    _db = db
