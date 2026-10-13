-- 0012: post-award control: variations (change orders) and progress for earned-value reporting.
CREATE TABLE variations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  title TEXT NOT NULL,
  description TEXT,
  instructed_by TEXT,
  instruction_ref TEXT,
  time_days TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',      -- Draft / Pending Review / Approved / Rejected
  priced_json TEXT,                          -- frozen pricing at submission (lines, markup, totals)
  amount_pre_markup TEXT,
  amount TEXT,
  created_by TEXT,
  created_at TEXT,
  submitted_at TEXT,
  decided_by TEXT,
  decided_at TEXT,
  decision_comments TEXT
);

CREATE TABLE variation_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  variation_id TEXT NOT NULL REFERENCES variations(id),
  line_no INTEGER NOT NULL,
  resource_id TEXT NOT NULL,
  description TEXT,
  direction TEXT NOT NULL DEFAULT 'add',      -- add / omit
  quantity TEXT NOT NULL,
  unit TEXT,
  UNIQUE(variation_id, line_no)
);

CREATE TABLE task_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  task_code TEXT NOT NULL,
  as_of TEXT NOT NULL,
  pct TEXT NOT NULL,
  basis TEXT NOT NULL,
  entered_by TEXT NOT NULL,
  entered_at TEXT NOT NULL
);
CREATE INDEX ix_task_progress ON task_progress(project_id, task_code, as_of);
