-- Core: identity, audit, approvals, taxonomy, reference data, projects
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('Estimator','Procurement Reviewer','Commercial Approver','Administrator','Viewer','AI Assistant')),
  password_hash TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  is_ai INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT,
  updated_by TEXT
);

-- Hash-chained (tamper-EVIDENT, not tamper-proof) audit trail
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  actor_role TEXT,
  project_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  comment TEXT,
  prev_hash TEXT,
  hash TEXT NOT NULL
);
CREATE INDEX ix_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX ix_audit_project ON audit_log(project_id);

CREATE TABLE approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  version TEXT,
  reviewer TEXT NOT NULL,
  reviewer_role TEXT NOT NULL,
  action TEXT NOT NULL,           -- Approve / Reject / Approve Provisional / Request Changes / Accept Exception ...
  ts TEXT NOT NULL,
  previous_value TEXT,
  approved_value TEXT,
  evidence TEXT,
  comments TEXT,
  override_reason TEXT
);
CREATE INDEX ix_approvals_entity ON approvals(entity_type, entity_id);

CREATE TABLE change_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  field TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  reason TEXT,
  evidence TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  decided_by TEXT,
  decided_at TEXT,
  decision_comment TEXT
);
CREATE INDEX ix_cr_project ON change_requests(project_id, status);

CREATE TABLE cost_codes (
  code TEXT PRIMARY KEY,
  parent_code TEXT REFERENCES cost_codes(code),
  level INTEGER NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  name_ar TEXT,
  short_name TEXT,
  default_unit TEXT,
  description TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  is_system INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_cc_parent ON cost_codes(parent_code);

CREATE TABLE units (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  dimension TEXT NOT NULL,
  to_base TEXT NOT NULL,
  synonyms TEXT,
  ambiguous_synonyms TEXT,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE regions (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_ar TEXT,
  parent_code TEXT,
  kind TEXT,
  notes TEXT
);

-- Tax categories are date-sensitive and require verification before use in an approved estimate
CREATE TABLE tax_categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  rate_pct TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  recoverable INTEGER NOT NULL DEFAULT 1,
  source_ref TEXT,
  verification_note TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(code, valid_from)
);

CREATE TABLE fx_rates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_ccy TEXT NOT NULL,
  to_ccy TEXT NOT NULL,
  rate TEXT NOT NULL,
  rate_date TEXT NOT NULL,
  valid_until TEXT,
  source TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE sources (
  source_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  organisation TEXT,
  url TEXT,
  type TEXT,
  date_accessed TEXT,
  publication_date TEXT,
  geographic_relevance TEXT,
  currency TEXT,
  unit_price_basis TEXT,
  applicable_trades TEXT,
  licence_reuse_conditions TEXT,
  extraction_method TEXT,
  access_status TEXT,
  limitations TEXT,
  confidence TEXT,
  data_collected TEXT
);

CREATE TABLE commercial_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  project_id TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(code, version)
);

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  client TEXT,
  location TEXT,
  region TEXT NOT NULL DEFAULT 'KSA-ALL',
  currency TEXT NOT NULL DEFAULT 'SAR',
  design_stage TEXT,
  status TEXT NOT NULL DEFAULT 'Active',         -- Active / Archived
  is_demo INTEGER NOT NULL DEFAULT 0,
  tax_category TEXT,
  commercial_policy_id INTEGER REFERENCES commercial_policies(id),
  rate_as_of_date TEXT,
  tender_ref TEXT,
  submission_date TEXT,
  notes TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  archived_at TEXT
);

CREATE TABLE ai_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT,
  kind TEXT NOT NULL,
  subject_type TEXT,
  subject_id TEXT,
  payload_json TEXT NOT NULL,
  source_refs TEXT,
  confidence TEXT,
  produced_by TEXT NOT NULL,          -- 'ai:<model>' or 'heuristic'
  status TEXT NOT NULL DEFAULT 'Pending Review',
  created_at TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_comment TEXT
);
