-- 0007: numbered project workspaces, document index, estimate input snapshots,
--       public-source import manifests, rate candidates (review queue), index observations, source access log.

ALTER TABLE projects ADD COLUMN workspace_slug TEXT;
ALTER TABLE projects ADD COLUMN workspace_path TEXT;       -- relative to settings.workspaces_dir (e.g. PRJ-0002-office-fitout)
ALTER TABLE projects ADD COLUMN project_type TEXT;
ALTER TABLE projects ADD COLUMN trades TEXT;               -- JSON list of trade/division codes
ALTER TABLE projects ADD COLUMN drawing_revision TEXT;     -- human-recorded approved revision labels (free text)
ALTER TABLE projects ADD COLUMN spec_revision TEXT;
CREATE UNIQUE INDEX ux_projects_workspace_path ON projects(workspace_path) WHERE workspace_path IS NOT NULL;

CREATE TABLE project_documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  rel_path TEXT NOT NULL,                  -- relative to the project workspace
  file_name TEXT NOT NULL,
  file_type TEXT,
  size_bytes INTEGER,
  modified_at TEXT,
  sha256 TEXT,
  area TEXT,                               -- numbered workspace folder it lives in
  category TEXT,                           -- document category guess (drawing/specification/boq/...) - filename based
  trade_hint TEXT,                         -- trade guess from file name only
  revision TEXT,                           -- only when reliably identifiable from the file name
  extraction_status TEXT NOT NULL,         -- Extracted / Not text-extracted / Extraction error / Missing
  extraction_error TEXT,
  extract_version INTEGER NOT NULL DEFAULT 0,
  extract_path TEXT,                       -- relative to workspace, under "2. AI Context"
  text_chars INTEGER,
  review_status TEXT NOT NULL DEFAULT 'New',   -- New / Reviewed / Source changed - review / Missing
  first_indexed_at TEXT NOT NULL,
  last_indexed_at TEXT NOT NULL,
  UNIQUE(project_id, rel_path)
);

CREATE TABLE estimate_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  estimate_version_id INTEGER NOT NULL UNIQUE REFERENCES estimate_versions(id),
  project_id TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,             -- every rate/assumption/assembly/policy/tax/fx version the estimate used
  sha256 TEXT NOT NULL,
  file_path TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE import_manifests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                      -- rates / index / web-discovery
  adapter TEXT,
  source_id TEXT,
  source_name TEXT,
  source_url TEXT,
  original_path TEXT,
  stored_path TEXT,
  sha256 TEXT,
  description TEXT,
  imported_at TEXT NOT NULL,
  imported_by TEXT NOT NULL,
  dry_run INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,                    -- Dry run / Imported / Rejected
  parsing_json TEXT,
  accepted_rows INTEGER NOT NULL DEFAULT 0,
  rejected_rows INTEGER NOT NULL DEFAULT 0,
  errors_json TEXT,
  candidate_ids_json TEXT,
  manifest_path TEXT
);
CREATE UNIQUE INDEX ux_import_manifest_hash ON import_manifests(sha256, kind) WHERE dry_run=0 AND status='Imported';

CREATE TABLE rate_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_ref TEXT NOT NULL UNIQUE,      -- RC-000001
  resource_id TEXT REFERENCES resources(id),          -- NULL until matched by a human
  suggested_resource_id TEXT,
  description TEXT,
  specification TEXT,
  source_type TEXT NOT NULL,               -- Manual dataset / Supplier website / Official statistics / Quotation / Historical project
  source_name TEXT,
  source_id TEXT,
  source_url TEXT,                         -- exact URL or uploaded-file reference
  retrieved_at TEXT,
  source_published_at TEXT,                -- publication date at the source, when stated
  effective_date TEXT,
  valid_until TEXT,
  geography TEXT,
  currency TEXT,
  unit TEXT,
  original_price TEXT,                     -- as found at the source - NEVER overwritten
  original_currency TEXT,
  original_unit TEXT,
  normalised_price TEXT,                   -- only when normalisation inputs are known and recorded
  normalisation_method TEXT,
  normalisation_json TEXT,
  tax_basis TEXT,                          -- Included / Excluded / Unknown
  delivery_basis TEXT,                     -- Supply only / Delivered / Installed / Unknown
  installation_included TEXT,
  price_kind TEXT,                         -- List price / Promotional / Quoted / Quote required / Specification only / Unknown
  confidence TEXT NOT NULL DEFAULT 'Unverified',
  extraction_method TEXT,
  evidence_snippet TEXT,
  flags_json TEXT,                         -- STALE / CONTRADICTORY / VAT_UNKNOWN / ...
  queue TEXT NOT NULL DEFAULT 'New',       -- New / Updated / Conflicting / Expired / Requires Verification
  status TEXT NOT NULL DEFAULT 'Pending Review',   -- Pending Review / Needs Verification / Approved for Publication / Rejected / Published
  reviewer TEXT,
  reviewed_at TEXT,
  review_comments TEXT,
  manifest_id INTEGER REFERENCES import_manifests(id),
  published_rate_id INTEGER REFERENCES resource_rates(id),
  published_by TEXT,
  published_at TEXT,
  row_hash TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX ix_rate_candidates_status ON rate_candidates(status, queue);

CREATE TABLE index_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT,
  dataset TEXT NOT NULL,
  series TEXT NOT NULL,                    -- e.g. "Labor Costs"
  measure TEXT NOT NULL,                   -- Index / M-o-M / Y-o-Y
  period TEXT NOT NULL,                    -- YYYY-MM
  value TEXT NOT NULL,                     -- exact text as published
  unit TEXT,
  manifest_id INTEGER REFERENCES import_manifests(id),
  retrieved_at TEXT,
  UNIQUE(dataset, series, measure, period, manifest_id)     -- revisions are kept as new rows, never overwritten
);

CREATE TABLE source_access_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL,
  url TEXT,
  attempted_at TEXT NOT NULL,
  outcome TEXT NOT NULL,                   -- OK / BLOCKED / ERROR / NOT_MODIFIED / SKIPPED / DRY_RUN
  http_status INTEGER,
  error TEXT,
  bytes INTEGER,
  note TEXT
);
CREATE INDEX ix_source_access_provider ON source_access_log(provider, attempted_at);
