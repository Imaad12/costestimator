CREATE TABLE clarifications (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  question TEXT NOT NULL,
  trade TEXT,
  boq_item_key TEXT,
  doc_ref TEXT,
  reason TEXT,
  commercial_impact TEXT,
  cost_exposure TEXT,
  proposed_wording TEXT,
  owner TEXT,
  status TEXT NOT NULL DEFAULT 'Open',     -- Open / Submitted / Resolved / Withdrawn
  client_response TEXT,
  resolution_evidence TEXT,
  resolution_date TEXT,
  suggested_by TEXT,
  created_by TEXT,
  created_at TEXT,
  resolved_by TEXT
);

CREATE TABLE scope_register (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL CHECK (kind IN ('inclusion','exclusion','qualification')),
  description TEXT NOT NULL,
  trade TEXT,
  boq_item_key TEXT,
  cost_code TEXT,
  rationale TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE risks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  title TEXT NOT NULL,
  description TEXT,
  trade TEXT,
  probability TEXT,
  impact TEXT,
  cost_exposure TEXT,
  mitigation TEXT,
  owner TEXT,
  status TEXT NOT NULL DEFAULT 'Open',
  created_by TEXT,
  created_at TEXT
);

CREATE TABLE offers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  version_no INTEGER NOT NULL,
  estimate_version_id INTEGER,
  total_pre_tax TEXT,
  tax_total TEXT,
  total_incl_tax TEXT,
  validity_days TEXT,
  payment_terms TEXT,
  inclusions_json TEXT,
  exclusions_json TEXT,
  clarifications_json TEXT,
  schedule_hash TEXT,
  file_path TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',
  created_by TEXT,
  created_at TEXT,
  UNIQUE(project_id, version_no)
);

CREATE TABLE recon_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  ts TEXT NOT NULL,
  run_by TEXT,
  inputs_hash TEXT,
  summary_json TEXT
);

CREATE TABLE recon_findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES recon_runs(id),
  project_id TEXT NOT NULL,
  rule_code TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  entity_type TEXT,
  entity_id TEXT,
  fingerprint TEXT NOT NULL,
  financial_impact TEXT,
  owner TEXT,
  status TEXT NOT NULL DEFAULT 'Open',     -- Open / Accepted Exception / Resolved
  exception_id INTEGER
);
CREATE INDEX ix_findings_run ON recon_findings(run_id);

CREATE TABLE recon_exceptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  rule_code TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  fingerprint TEXT NOT NULL,
  reason TEXT NOT NULL,
  accepted_by TEXT NOT NULL,
  accepted_role TEXT,
  accepted_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE exports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  submission_ready INTEGER NOT NULL DEFAULT 0,
  estimate_version_id INTEGER,
  file_path TEXT,
  sha256 TEXT,
  created_by TEXT,
  created_at TEXT,
  approval_ref TEXT
);
