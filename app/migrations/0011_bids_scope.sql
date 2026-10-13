-- 0011: bid evaluation scores, long-lead tracking, package scope / interface matrix.
CREATE TABLE bid_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT NOT NULL,
  quotation_id TEXT NOT NULL,
  criteria_code TEXT NOT NULL,
  criterion_id TEXT NOT NULL,
  score TEXT NOT NULL,
  evidence TEXT NOT NULL,
  scored_by TEXT NOT NULL,
  scored_at TEXT NOT NULL
);
CREATE INDEX ix_bid_scores ON bid_scores(package_id, quotation_id, criterion_id);

CREATE TABLE long_lead_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT,
  description TEXT NOT NULL,
  supplier_id TEXT,
  lead_time_weeks TEXT NOT NULL,
  required_on_site TEXT NOT NULL,
  planned_order_date TEXT,
  actual_order_date TEXT,
  vendor_data_due TEXT,
  vendor_data_received TEXT,
  notes TEXT,
  created_by TEXT,
  created_at TEXT
);

CREATE TABLE package_scope (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT NOT NULL,
  ref_type TEXT NOT NULL,                  -- boq_item / cost_prefix
  ref TEXT NOT NULL,
  responsibility TEXT NOT NULL,            -- included / excluded / by_others
  counterpart_package TEXT,                -- required for by_others
  note TEXT,
  created_by TEXT,
  created_at TEXT,
  UNIQUE(project_id, package_id, ref_type, ref)
);
