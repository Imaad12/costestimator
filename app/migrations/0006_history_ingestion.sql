CREATE TABLE actual_costs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  cost_code TEXT,
  resource_id TEXT,
  description TEXT,
  actual_amount TEXT,
  actual_quantity TEXT,
  actual_hours TEXT,
  unit TEXT,
  cost_date TEXT,
  region TEXT,
  source TEXT NOT NULL,                 -- where this actual came from (ledger ref etc.) - required
  entered_by TEXT NOT NULL,
  entered_at TEXT NOT NULL
);

CREATE TABLE dataset_imports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT,
  file_name TEXT NOT NULL,
  sha256 TEXT,
  kind TEXT NOT NULL,                   -- rates / resources
  status TEXT NOT NULL DEFAULT 'Staged',  -- Staged / Published / Rejected
  summary_json TEXT,
  imported_by TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  published_by TEXT,
  published_at TEXT
);

CREATE TABLE rate_staging (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_id INTEGER NOT NULL REFERENCES dataset_imports(id),
  row_no INTEGER,
  resource_id TEXT,
  description TEXT,
  unit TEXT,
  unit_price TEXT,
  currency TEXT,
  rate_type TEXT,
  region TEXT,
  price_date TEXT,
  valid_until TEXT,
  source_id TEXT,
  supplier_id TEXT,
  tax_basis TEXT,
  delivery_basis TEXT,
  raw_json TEXT,
  issues_json TEXT,
  decision TEXT NOT NULL DEFAULT 'Pending',   -- Pending / Accept / Reject
  published_rate_id INTEGER
);
