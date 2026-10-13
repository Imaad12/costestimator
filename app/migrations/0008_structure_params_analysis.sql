-- 0008: WBS/CBS structure, governed parameters (human-approved numeric inputs), analysis runs (non-authoritative outputs).
-- Nothing here carries a price or a default value: every governed parameter is user-supplied and goes through Draft -> Pending Review -> Approved.

CREATE TABLE wbs_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  code TEXT NOT NULL,
  parent_code TEXT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'area',        -- area / unit / system / phase / package / other (free classification)
  created_by TEXT,
  created_at TEXT,
  UNIQUE(project_id, code)
);

CREATE TABLE boq_wbs (
  project_id TEXT NOT NULL REFERENCES projects(id),
  item_key TEXT NOT NULL,
  wbs_code TEXT NOT NULL,
  assigned_by TEXT,
  assigned_at TEXT,
  PRIMARY KEY (project_id, item_key)
);

-- Cross-walk from the internal cost-code tree to a client / owner coding system (loaded from the client's own list; nothing is guessed).
CREATE TABLE code_crosswalk (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  system TEXT NOT NULL,                     -- name of the client coding system
  client_code TEXT NOT NULL,
  client_name TEXT,
  cost_code TEXT NOT NULL,                  -- internal cost code or prefix (longest prefix wins)
  created_by TEXT,
  created_at TEXT,
  UNIQUE(project_id, system, client_code, cost_code)
);

-- Versioned, human-approved numeric inputs of several kinds (productivity factors, plant hire terms, statutory labour components, MTO factors,
-- benchmark ranges, calendars ...). data_json is validated per kind; project_id NULL = company-wide.
CREATE TABLE governed_params (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT REFERENCES projects(id),
  kind TEXT NOT NULL,
  code TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'Draft',
  data_json TEXT NOT NULL,
  source TEXT,
  basis_note TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT
);
CREATE UNIQUE INDEX ux_governed_params ON governed_params(COALESCE(project_id,''), kind, code, version);
CREATE INDEX ix_governed_kind ON governed_params(kind, status);

-- Immutable analysis outputs (loading histograms, Monte Carlo, cash flow ...). They are views over inputs, never approved data.
CREATE TABLE analysis_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL,
  params_json TEXT,
  inputs_hash TEXT,
  result_json TEXT NOT NULL,
  notes TEXT,
  created_by TEXT,
  created_at TEXT
);
CREATE INDEX ix_analysis_runs ON analysis_runs(project_id, kind);

ALTER TABLE schedule_tasks ADD COLUMN wbs_code TEXT;
ALTER TABLE schedule_tasks ADD COLUMN snet TEXT;     -- start-no-earlier-than: working-day offset or ISO date (needs a calendar)
ALTER TABLE schedule_tasks ADD COLUMN fnlt TEXT;     -- finish-no-later-than

-- Quantified risk register fields (human-entered; Monte Carlo only reads them).
ALTER TABLE risks ADD COLUMN category TEXT;
ALTER TABLE risks ADD COLUMN prob_pct TEXT;
ALTER TABLE risks ADD COLUMN cost_low TEXT;
ALTER TABLE risks ADD COLUMN cost_likely TEXT;
ALTER TABLE risks ADD COLUMN cost_high TEXT;
ALTER TABLE risks ADD COLUMN schedule_days TEXT;
ALTER TABLE risks ADD COLUMN response TEXT;
