-- 0015: end-to-end closure: assumptions governance extensions, workforce/productivity/work activities, tender registers, document packs.
-- Additive only. No numeric defaults are seeded: every norm, profile and crew split is entered (and approved) by a person.

-- ---------------------------------------------------------------- assumptions register: category, origin, impact, uncertainty
ALTER TABLE assumptions ADD COLUMN category TEXT;                 -- one of the 17 register categories (services/assumptions.CATEGORIES)
ALTER TABLE assumptions ADD COLUMN origin TEXT NOT NULL DEFAULT 'manual';   -- manual | import | seed | calculated | ai | synthetic
ALTER TABLE assumptions ADD COLUMN reason TEXT;
ALTER TABLE assumptions ADD COLUMN business_impact TEXT;
ALTER TABLE assumptions ADD COLUMN uncertainty TEXT;
ALTER TABLE assumptions ADD COLUMN consequence_if_missing TEXT;
ALTER TABLE assumptions ADD COLUMN affects TEXT;                  -- comma separated estimate components this value feeds
ALTER TABLE assumptions ADD COLUMN reviewed_by TEXT;
ALTER TABLE assumptions ADD COLUMN reviewed_at TEXT;
ALTER TABLE assumptions ADD COLUMN supersedes_version INTEGER;
ALTER TABLE project_assumptions ADD COLUMN approved_value_hash TEXT;

-- Approved / superseded assumption versions are immutable at the database layer too. This is a GUARD against application bugs and casual SQL,
-- NOT tamper-proofing: anyone with write access to the database file can drop these triggers (see docs/ASSUMPTIONS_GOVERNANCE_AND_SECURITY_AUDIT.md).
CREATE TRIGGER trg_assumption_immutable BEFORE UPDATE ON assumptions
WHEN OLD.status IN ('Approved','Superseded') AND (
     NEW.id IS NOT OLD.id OR NEW.version IS NOT OLD.version OR NEW.name IS NOT OLD.name OR NEW.default_value IS NOT OLD.default_value
  OR NEW.unit IS NOT OLD.unit OR NEW.value_type IS NOT OLD.value_type OR NEW.engine_key IS NOT OLD.engine_key OR NEW.source IS NOT OLD.source
  OR NEW.evidence IS NOT OLD.evidence OR NEW.created_by IS NOT OLD.created_by OR NEW.approved_by IS NOT OLD.approved_by
  OR NEW.approved_at IS NOT OLD.approved_at OR NEW.is_synthetic IS NOT OLD.is_synthetic OR NEW.origin IS NOT OLD.origin
  OR (OLD.status = 'Superseded' AND NEW.status IS NOT 'Superseded')
  OR (OLD.status = 'Approved' AND NEW.status NOT IN ('Approved','Superseded','Expired')))
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved assumption versions cannot be changed; create a new version'); END;

CREATE TRIGGER trg_assumption_nodelete BEFORE DELETE ON assumptions
WHEN OLD.status IN ('Approved','Superseded')
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved assumption versions cannot be deleted'); END;

CREATE TRIGGER trg_project_assumption_immutable BEFORE UPDATE ON project_assumptions
WHEN OLD.status IN ('Approved','Superseded') AND (
     NEW.override_value IS NOT OLD.override_value OR NEW.reason IS NOT OLD.reason OR NEW.approved_by IS NOT OLD.approved_by
  OR NEW.created_by IS NOT OLD.created_by OR NEW.version_no IS NOT OLD.version_no OR NEW.base_version IS NOT OLD.base_version
  OR (OLD.status = 'Superseded' AND NEW.status IS NOT 'Superseded')
  OR (OLD.status = 'Approved' AND NEW.status NOT IN ('Approved','Superseded')))
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved project overrides cannot be changed; propose a new override'); END;

CREATE TRIGGER trg_project_assumption_nodelete BEFORE DELETE ON project_assumptions
WHEN OLD.status IN ('Approved','Superseded')
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved project overrides cannot be deleted'); END;

-- ---------------------------------------------------------------- governed productivity norms (versioned, sourced, human-approved)
CREATE TABLE productivity_norms (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  trade TEXT NOT NULL,
  activity TEXT NOT NULL,
  cost_prefix TEXT,
  output_unit TEXT NOT NULL,                                       -- the BOQ/take-off unit the norm is expressed per
  basis TEXT NOT NULL CHECK (basis IN ('labour_hours_per_unit','crew_output_per_crew_day')),
  value TEXT NOT NULL,                                             -- exact decimal: hours per unit, or units per crew-day
  includes_productivity_factors INTEGER NOT NULL DEFAULT 0,        -- 1: crew output already includes site factors (no second factor may be applied)
  crew_json TEXT NOT NULL,                                         -- role -> head-count of one crew (the crew the norm refers to)
  applicability_json TEXT,                                         -- region, project type, conditions
  exclusions TEXT,
  source TEXT, evidence TEXT,
  confidence TEXT NOT NULL DEFAULT 'Low',
  evidence_status TEXT NOT NULL DEFAULT 'unverified' CHECK (evidence_status IN ('unverified','verified','synthetic')),
  origin TEXT NOT NULL DEFAULT 'user' CHECK (origin IN ('user','system','import','synthetic')),
  status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft','Proposed','Imported - Unverified','Pending Review','Approved','Rejected','Superseded')),
  effective_from TEXT, review_by TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_by TEXT, created_at TEXT, reviewed_by TEXT, approved_by TEXT, approved_at TEXT,
  UNIQUE(id, version)
);
CREATE TRIGGER trg_norm_immutable BEFORE UPDATE ON productivity_norms
WHEN OLD.status IN ('Approved','Superseded') AND (
     NEW.id IS NOT OLD.id OR NEW.version IS NOT OLD.version OR NEW.value IS NOT OLD.value OR NEW.basis IS NOT OLD.basis OR NEW.crew_json IS NOT OLD.crew_json
  OR NEW.output_unit IS NOT OLD.output_unit OR NEW.source IS NOT OLD.source OR NEW.created_by IS NOT OLD.created_by OR NEW.approved_by IS NOT OLD.approved_by
  OR NEW.is_synthetic IS NOT OLD.is_synthetic OR NEW.includes_productivity_factors IS NOT OLD.includes_productivity_factors
  OR (OLD.status = 'Superseded' AND NEW.status IS NOT 'Superseded') OR (OLD.status = 'Approved' AND NEW.status NOT IN ('Approved','Superseded')))
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved productivity norms cannot be changed; create a new version'); END;
CREATE TRIGGER trg_norm_nodelete BEFORE DELETE ON productivity_norms WHEN OLD.status IN ('Approved','Superseded')
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved productivity norms cannot be deleted'); END;

-- ---------------------------------------------------------------- workforce profiles (configurable planning assumptions - NOT industry categories)
CREATE TABLE workforce_profiles (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  archetype TEXT NOT NULL CHECK (archetype IN ('sme','mid','large','enterprise','custom')),
  name TEXT NOT NULL,
  min_workers INTEGER, max_workers INTEGER,                        -- archetype band (company planning band)
  roles_json TEXT NOT NULL DEFAULT '{}',                           -- direct roles: role -> available head-count (per shift)
  indirect_json TEXT NOT NULL DEFAULT '{}',                        -- supervision / QC / HSE / engineering etc. head-count
  shifts INTEGER NOT NULL DEFAULT 1,
  night_shift_efficiency_pct TEXT,                                 -- required when shifts > 1
  attendance_pct TEXT, availability_pct TEXT,
  productive_hours_per_shift TEXT,
  overtime_hours_per_day TEXT, overtime_efficiency_pct TEXT,
  work_fronts INTEGER,
  mobilisation_wd INTEGER NOT NULL DEFAULT 0,                      -- working days from project start before the workforce is available
  subcontract_capacity_json TEXT NOT NULL DEFAULT '{}',            -- package/role -> capacity head-count
  role_day_cost_json TEXT,                                         -- optional role -> cost per worker-day (each entered, sourced and approved by a person)
  label TEXT NOT NULL DEFAULT 'Configurable company planning assumption - not an industry-standard workforce category',
  source TEXT, is_synthetic INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft','Pending Review','Approved','Rejected','Superseded')),
  created_by TEXT, created_at TEXT, approved_by TEXT, approved_at TEXT, notes TEXT,
  UNIQUE(id, version)
);
CREATE TRIGGER trg_workforce_immutable BEFORE UPDATE ON workforce_profiles
WHEN OLD.status IN ('Approved','Superseded') AND (
     NEW.id IS NOT OLD.id OR NEW.version IS NOT OLD.version OR NEW.roles_json IS NOT OLD.roles_json OR NEW.indirect_json IS NOT OLD.indirect_json
  OR NEW.shifts IS NOT OLD.shifts OR NEW.work_fronts IS NOT OLD.work_fronts OR NEW.productive_hours_per_shift IS NOT OLD.productive_hours_per_shift
  OR NEW.created_by IS NOT OLD.created_by OR NEW.approved_by IS NOT OLD.approved_by OR NEW.attendance_pct IS NOT OLD.attendance_pct
  OR (OLD.status = 'Superseded' AND NEW.status IS NOT 'Superseded') OR (OLD.status = 'Approved' AND NEW.status NOT IN ('Approved','Superseded')))
BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_RECORD: approved workforce profiles cannot be changed; create a new version'); END;

-- ---------------------------------------------------------------- project work activities (programme input from a person; quantity is read from the BOQ)
CREATE TABLE work_activities (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  wbs_code TEXT, cost_code TEXT,
  boq_item_key TEXT,                                               -- human-measured quantity is taken from this BOQ item (never invented here)
  norm_id TEXT,                                                    -- productivity norm id (the latest version eligible for the run is used)
  crews INTEGER NOT NULL DEFAULT 1,
  work_fronts INTEGER NOT NULL DEFAULT 1,
  fixed_days_json TEXT NOT NULL DEFAULT '{}',                      -- mobilisation / setup / curing / testing / inspection (working days, entered by a person)
  predecessors TEXT,
  long_lead_id TEXT,                                               -- long_lead_items.id that must be on site before the activity starts
  priority INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_by TEXT, created_at TEXT,
  UNIQUE(project_id, code)
);

-- programme baselines produced by the engine and approved by a person
CREATE TABLE programme_baselines (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  version_no INTEGER NOT NULL,
  profile_id TEXT, profile_version INTEGER,
  start_date TEXT,
  result_json TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  provisional INTEGER NOT NULL DEFAULT 0,                          -- 1 when any norm / profile is not Approved
  status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft','Pending Review','Approved','Rejected','Superseded')),
  created_by TEXT, created_at TEXT, approved_by TEXT, approved_at TEXT,
  UNIQUE(project_id, version_no)
);

-- ---------------------------------------------------------------- tender registers
CREATE TABLE tender_enquiries (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  customer_name TEXT NOT NULL,
  customer_is_synthetic INTEGER NOT NULL DEFAULT 0,
  title TEXT NOT NULL,
  received_date TEXT, tender_deadline TEXT, submission_instructions TEXT,
  brief TEXT, scope_summary TEXT,
  status TEXT NOT NULL DEFAULT 'Received',
  created_by TEXT, created_at TEXT
);

CREATE TABLE tender_documents (                                     -- documents RECEIVED from the customer (intake register)
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  doc_ref TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  title TEXT NOT NULL,
  revision TEXT NOT NULL,
  source TEXT, received_date TEXT, applicability TEXT,
  status TEXT NOT NULL DEFAULT 'Current' CHECK (status IN ('Current','Superseded','Missing','Withdrawn')),
  content_status TEXT NOT NULL DEFAULT 'registered_only' CHECK (content_status IN ('registered_only','parsed','reviewed')),   -- never claim interpretation without it
  supersedes_pk INTEGER,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT, created_at TEXT,
  UNIQUE(project_id, doc_ref, revision)
);

CREATE TABLE tender_queries (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  register TEXT NOT NULL CHECK (register IN ('technical','commercial','boq_discrepancy','scope_exclusion','design_interface','missing_input','assumption_confirmation','supplier')),
  discipline TEXT, responsible_party TEXT,
  related_json TEXT NOT NULL DEFAULT '{}',                          -- boq items, documents + revisions
  question TEXT NOT NULL,
  why TEXT, impact_json TEXT NOT NULL DEFAULT '{}',                 -- technical / cost / programme / safety / compliance
  response_due TEXT, options TEXT, recommendation TEXT,
  status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft','Approved to Issue','Issued','Answered','Closed','Withdrawn')),
  response_text TEXT, response_by TEXT, response_date TEXT, response_is_synthetic INTEGER NOT NULL DEFAULT 0,
  cost_impact TEXT, time_impact_days TEXT,
  detector_key TEXT,                                                 -- de-duplication key when the draft was generated from a detected condition
  generated_by TEXT NOT NULL DEFAULT 'user',
  blocks_submission INTEGER NOT NULL DEFAULT 1,
  created_by TEXT, created_at TEXT, approved_by TEXT, approved_at TEXT,
  UNIQUE(project_id, detector_key)
);

CREATE TABLE tender_register_items (                                -- compliance matrix, ITP, method statements, HSE risks, permits, submittals, T&C, NCR structure, bid/no-bid ...
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  register TEXT NOT NULL,
  item_key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft','Pending Review','Approved','Rejected')),
  review_note TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT, created_at TEXT, approved_by TEXT, approved_at TEXT,
  UNIQUE(project_id, register, item_key)
);

-- ---------------------------------------------------------------- standards / source register
CREATE TABLE standards_register (
  id TEXT PRIMARY KEY,
  topic TEXT NOT NULL, title TEXT NOT NULL, publisher TEXT, url TEXT,
  edition TEXT, access_date TEXT, clause_or_page TEXT, scope TEXT, limitations TEXT,
  verification_status TEXT NOT NULL CHECK (verification_status IN ('Verified - primary source read','Partially verified - secondary source','Not verified - requires human acquisition')),
  paraphrase TEXT, notes TEXT,
  created_by TEXT, created_at TEXT
);

-- ---------------------------------------------------------------- generated tender / handover packs
CREATE TABLE tender_packs (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL CHECK (kind IN ('tender','handover')),
  revision INTEGER NOT NULL,
  estimate_version_id INTEGER, estimate_fingerprint TEXT,
  classification TEXT NOT NULL,                                     -- production | demonstration | not_ready  (from services/readiness)
  status_label TEXT NOT NULL,
  validation_json TEXT, manifest_sha256 TEXT, out_dir TEXT,
  hypothetical INTEGER NOT NULL DEFAULT 0,                          -- 1: simulated post-award handover
  created_by TEXT, created_at TEXT,
  UNIQUE(project_id, kind, revision)
);

CREATE TABLE generated_documents (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  pack_pk INTEGER NOT NULL REFERENCES tender_packs(pk),
  doc_code TEXT NOT NULL,                                           -- catalogue code, e.g. T-16
  doc_id TEXT NOT NULL,                                             -- stable document id, e.g. PRJ-9101-T16
  title TEXT NOT NULL,
  template_id TEXT NOT NULL, template_version TEXT NOT NULL,
  revision INTEGER NOT NULL,
  status TEXT NOT NULL,                                             -- Draft | For Review | Preliminary | BLOCKED | Approved for Submission
  applicability TEXT NOT NULL, applicability_reason TEXT,
  format TEXT, path TEXT, sha256 TEXT, bytes INTEGER,
  blocked_reason TEXT,
  refs_json TEXT,                                                   -- stable ids of related documents / queries / assumptions
  facts_json TEXT,                                                  -- the figures printed (for cross-document consistency checks)
  created_at TEXT,
  UNIQUE(pack_pk, doc_code)
);

-- ---------------------------------------------------------------- ownership of follow-up actions (handover)
CREATE TABLE open_actions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  description TEXT NOT NULL, owner TEXT, due TEXT, source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','Done','Cancelled')),
  created_by TEXT, created_at TEXT
);
