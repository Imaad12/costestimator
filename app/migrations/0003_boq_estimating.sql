-- BOQ, takeoff, estimating state
CREATE TABLE boq_imports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  revision TEXT,
  source_file TEXT NOT NULL,
  stored_path TEXT,
  sha256 TEXT,
  sheet TEXT,
  mapping_json TEXT,
  status TEXT NOT NULL DEFAULT 'Imported',
  summary_json TEXT,
  imported_by TEXT NOT NULL,
  imported_at TEXT NOT NULL
);

CREATE TABLE boq_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  import_id INTEGER REFERENCES boq_imports(id),
  item_key TEXT NOT NULL,               -- unique per project (item_code, with #n suffix for duplicates)
  item_code TEXT,
  item_type TEXT NOT NULL DEFAULT 'item' CHECK (item_type IN ('item','heading')),
  section TEXT,
  description TEXT,
  trade TEXT,
  unit_original TEXT,
  unit TEXT,                            -- canonical unit code or NULL when unknown/ambiguous
  unit_status TEXT NOT NULL DEFAULT 'ok',   -- ok / ambiguous / unknown / missing / approved_correction
  quantity_original TEXT,               -- immutable as-imported text
  quantity TEXT,                        -- value used in estimate (changes only via approved change request)
  client_rate TEXT,
  client_amount TEXT,
  drawing_ref TEXT,
  spec_ref TEXT,
  cost_code TEXT,
  revision TEXT,
  source_file TEXT,
  source_sheet TEXT,
  source_row INTEGER,
  issues_json TEXT,
  validation_status TEXT NOT NULL DEFAULT 'OK',   -- OK / Needs Review
  original_json TEXT,
  assembly_code TEXT,
  assembly_version INTEGER,
  mapping_status TEXT NOT NULL DEFAULT 'Unmapped',
  mapping_source TEXT,
  pricing_method TEXT NOT NULL DEFAULT 'unpriced',
  pricing_resource_id TEXT,
  pricing_amount TEXT,
  pricing_currency TEXT,
  pricing_status TEXT NOT NULL DEFAULT 'Draft',
  pricing_note TEXT,
  tax_category TEXT,
  status_in_revision TEXT NOT NULL DEFAULT 'Current',   -- Current / Missing in latest revision
  created_at TEXT,
  UNIQUE(project_id, item_key)
);
CREATE INDEX ix_boq_project ON boq_items(project_id);

CREATE TABLE boq_rejected_rows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id INTEGER NOT NULL REFERENCES boq_imports(id),
  project_id TEXT NOT NULL,
  source_file TEXT,
  source_sheet TEXT,
  source_row INTEGER,
  reason_code TEXT NOT NULL,
  reason TEXT NOT NULL,
  original_json TEXT
);

CREATE TABLE takeoff_resource_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  item_key TEXT NOT NULL,
  resource_id TEXT,
  description TEXT,
  quantity TEXT NOT NULL,
  unit TEXT,
  source_file TEXT,
  source_sheet TEXT,
  source_row INTEGER,
  notes TEXT
);
CREATE INDEX ix_takeoff_item ON takeoff_resource_lines(project_id, item_key);

-- Duration & indirects
CREATE TABLE project_durations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  months TEXT NOT NULL,
  source_type TEXT NOT NULL,          -- estimator_input / labour_derived / schedule_model / ai_proposal
  basis_note TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  proposed_by TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE schedule_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  task_code TEXT NOT NULL,
  name TEXT NOT NULL,
  duration_days TEXT NOT NULL,
  predecessors TEXT,
  cost_code TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(project_id, task_code)
);

CREATE TABLE indirect_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  code TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  method TEXT NOT NULL CHECK (method IN ('fixed','percent_of_direct','per_day','per_week','per_month','per_duration_month')),
  amount TEXT,                         -- NULL => input required (flagged, never defaulted to zero)
  quantity TEXT NOT NULL DEFAULT '1',
  allocation_method TEXT NOT NULL DEFAULT 'pro_rata_direct' CHECK (allocation_method IN ('pro_rata_direct','separate_line','direct_trade')),
  allocation_target TEXT,
  included_in_subcontract INTEGER NOT NULL DEFAULT 0,
  duration_override_months TEXT,
  currency TEXT NOT NULL DEFAULT 'SAR',
  status TEXT NOT NULL DEFAULT 'Draft',
  version INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  source TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(project_id, code, version)
);

-- Estimate versions (frozen results)
CREATE TABLE estimate_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  version_no INTEGER NOT NULL,
  label TEXT,
  state TEXT,                          -- Complete / Preliminary — Incomplete / ...
  status TEXT NOT NULL DEFAULT 'Draft',
  inputs_hash TEXT,
  totals_json TEXT,
  result_json TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  submitted_at TEXT,
  notes TEXT,
  UNIQUE(project_id, version_no)
);
