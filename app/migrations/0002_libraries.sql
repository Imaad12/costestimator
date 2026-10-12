-- Libraries: suppliers, resources, rates, assumptions, assemblies
CREATE TABLE suppliers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_ar TEXT,
  supplier_type TEXT,                 -- supplier / subcontractor / manufacturer
  trades TEXT,                        -- cost codes (comma separated)
  region TEXT,
  contact_name TEXT,
  contact_email TEXT,
  contact_phone TEXT,
  contact_source TEXT,                -- REQUIRED when any contact detail is present (traceable provenance)
  contact_permitted_use TEXT,
  qualification_status TEXT NOT NULL DEFAULT 'Pending Review',
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE resources (
  id TEXT PRIMARY KEY,
  resource_type TEXT NOT NULL CHECK (resource_type IN ('material','labour','plant','equipment','subcontract')),
  cost_code TEXT REFERENCES cost_codes(code),
  category TEXT,
  description TEXT NOT NULL,
  description_ar TEXT,
  aliases TEXT,
  specification TEXT,
  brand_requirements TEXT,
  unit TEXT NOT NULL REFERENCES units(code),
  currency TEXT NOT NULL DEFAULT 'SAR',
  geographic_applicability TEXT NOT NULL DEFAULT 'KSA-ALL',
  installation_included TEXT NOT NULL DEFAULT 'Unknown',        -- Yes / No / Unknown
  freight_unloading_included TEXT NOT NULL DEFAULT 'Unknown',
  tax_basis TEXT,
  delivery_basis TEXT,
  notes TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_by TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX ix_res_cc ON resources(cost_code);
CREATE INDEX ix_res_type ON resources(resource_type);

CREATE TABLE resource_rates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resource_id TEXT NOT NULL REFERENCES resources(id),
  version INTEGER NOT NULL,
  rate_type TEXT NOT NULL,
  unit_price TEXT,                      -- NULL for Missing Rate
  currency TEXT NOT NULL DEFAULT 'SAR',
  unit TEXT NOT NULL,
  region TEXT NOT NULL DEFAULT 'KSA-ALL',
  supplier_id TEXT REFERENCES suppliers(id),
  quotation_line_id INTEGER,
  source_id TEXT,
  evidence TEXT,
  price_date TEXT,
  valid_until TEXT,
  tax_basis TEXT,
  delivery_basis TEXT,
  installation_included TEXT,
  freight_included TEXT,
  confidence TEXT NOT NULL DEFAULT 'Unverified',
  status TEXT NOT NULL DEFAULT 'Draft',
  project_id TEXT,                      -- set for project-scoped (provisional) rates
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  components_json TEXT,                 -- labour / plant build-up inputs (see estimators/rate_build.py)
  notes TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  superseded_by INTEGER,
  UNIQUE(resource_id, version)
);
CREATE INDEX ix_rate_res ON resource_rates(resource_id, status);

CREATE TABLE assumptions (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  family TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  applies_to TEXT NOT NULL DEFAULT 'ALL',
  applicability TEXT,
  value_type TEXT NOT NULL DEFAULT 'text',
  default_value TEXT,
  unit TEXT,
  engine_key TEXT,
  mandatory_for_projects INTEGER NOT NULL DEFAULT 0,
  confidence TEXT NOT NULL DEFAULT 'Low',
  source TEXT,
  evidence TEXT,
  valid_from TEXT,
  valid_to TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  notes TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(id, version)
);
CREATE INDEX ix_asm_key ON assumptions(engine_key);

CREATE TABLE project_assumptions (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  assumption_id TEXT NOT NULL,
  base_version INTEGER,                 -- global assumption version adopted
  version_no INTEGER NOT NULL DEFAULT 1,
  override_value TEXT,                  -- NULL = adopt global default as-is
  has_override INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'Draft', -- status of the override / adoption
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(project_id, assumption_id, version_no)
);

CREATE TABLE assemblies (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  cost_code TEXT REFERENCES cost_codes(code),
  description TEXT NOT NULL,
  unit TEXT NOT NULL REFERENCES units(code),
  specification TEXT,
  applicability TEXT,
  source TEXT,
  confidence TEXT NOT NULL DEFAULT 'Unverified',
  status TEXT NOT NULL DEFAULT 'Draft',
  project_id TEXT,                      -- project-specific customisation
  cloned_from TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  revision_note TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(code, version)
);

CREATE TABLE assembly_lines (
  pk INTEGER PRIMARY KEY AUTOINCREMENT,
  assembly_pk INTEGER NOT NULL REFERENCES assemblies(pk) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,
  line_type TEXT NOT NULL CHECK (line_type IN ('material','labour','plant','equipment','subcontract','assembly','other')),
  resource_id TEXT REFERENCES resources(id),
  child_assembly_code TEXT,
  child_assembly_version INTEGER,
  description TEXT,
  factor TEXT,                           -- consumption per 1 unit of assembly; NULL => estimator input required
  factor_unit TEXT,                      -- defaults to resource unit
  factor_includes_waste INTEGER NOT NULL DEFAULT 0,
  waste_basis TEXT NOT NULL DEFAULT 'none' CHECK (waste_basis IN ('none','fixed_pct','assumption')),
  waste_value TEXT,                      -- percent points when fixed_pct
  waste_ref TEXT,                        -- assumption id when basis = assumption
  productivity_basis TEXT CHECK (productivity_basis IN ('paid_hours_per_unit','productive_hours_per_unit','output_per_crew_shift')),
  crew_json TEXT,                        -- [{"resource_id": "...", "count": 2}] for output_per_crew_shift
  shift_hours_ref TEXT,                  -- optional assumption id overriding engine key
  productive_hours_ref TEXT,
  overtime_share_pct TEXT,
  utilisation_basis TEXT NOT NULL DEFAULT 'none' CHECK (utilisation_basis IN ('none','fixed_pct','assumption')),
  utilisation_value TEXT,
  utilisation_ref TEXT,
  includes_labour INTEGER NOT NULL DEFAULT 0,
  includes_material INTEGER NOT NULL DEFAULT 0,
  includes_plant INTEGER NOT NULL DEFAULT 0,
  explicitly_separate INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  UNIQUE(assembly_pk, line_no)
);
