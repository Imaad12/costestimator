CREATE TABLE procurement_packages (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  trade TEXT,
  status TEXT NOT NULL DEFAULT 'Open',
  notes TEXT,
  created_by TEXT,
  created_at TEXT
);

CREATE TABLE procurement_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT REFERENCES procurement_packages(id),
  trade TEXT,
  item_id TEXT,                         -- resource id or BOQ item key
  boq_item_key TEXT,
  resource_id TEXT,
  description TEXT NOT NULL,
  specification TEXT,
  quantity TEXT,
  unit TEXT,
  delivery_location TEXT,
  required_date TEXT,
  preferred_suppliers TEXT,
  reason_code TEXT,                     -- MISSING_RATE / EXPIRED_RATE / UNAPPROVED_RATE / LOW_CONFIDENCE / SUBCONTRACT_PRICING / CLARIFY
  reason TEXT,
  estimated_exposure TEXT,
  priority TEXT,
  rfq_status TEXT NOT NULL DEFAULT 'Not Issued',
  response_deadline TEXT,
  quotation_status TEXT NOT NULL DEFAULT 'None',
  approval_status TEXT NOT NULL DEFAULT 'Pending Review',
  lead_time_days TEXT,
  closed INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  created_at TEXT,
  UNIQUE(project_id, resource_id, boq_item_key, reason_code)
);

CREATE TABLE rfqs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT REFERENCES procurement_packages(id),
  supplier_id TEXT REFERENCES suppliers(id),
  language TEXT NOT NULL DEFAULT 'en',
  subject TEXT,
  body TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',    -- Draft / Issued (manually) / Closed
  response_deadline TEXT,
  created_by TEXT,
  created_at TEXT,
  issued_at TEXT
);

CREATE TABLE rfq_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rfq_id TEXT NOT NULL REFERENCES rfqs(id),
  procurement_item_id TEXT NOT NULL REFERENCES procurement_items(id),
  UNIQUE(rfq_id, procurement_item_id)
);

CREATE TABLE quotations (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  package_id TEXT REFERENCES procurement_packages(id),
  supplier_id TEXT NOT NULL REFERENCES suppliers(id),
  reference TEXT,
  quote_date TEXT,
  valid_until TEXT,
  currency TEXT NOT NULL DEFAULT 'SAR',
  fx_rate_id INTEGER REFERENCES fx_rates(id),
  payment_terms TEXT,
  delivery_terms TEXT,
  tax_treatment TEXT,                   -- 'excl' / 'incl' / 'exempt' (+ rate on lines)
  tax_rate_pct TEXT,
  lead_time_days TEXT,
  exclusions TEXT,
  deviations TEXT,
  supporting_documents TEXT,
  source_file TEXT,
  extracted_by_ai INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'Draft',
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  entered_by TEXT,
  entered_at TEXT,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE quotation_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quotation_id TEXT NOT NULL REFERENCES quotations(id),
  line_no INTEGER NOT NULL,
  procurement_item_id TEXT REFERENCES procurement_items(id),
  description TEXT,
  specification TEXT,
  quantity TEXT,
  unit TEXT,
  unit_rate TEXT,
  discount_pct TEXT,
  delivery_included TEXT DEFAULT 'Unknown',
  unloading_included TEXT DEFAULT 'Unknown',
  installation_included TEXT DEFAULT 'Unknown',
  tax_included TEXT DEFAULT 'Unknown',
  lead_time_days TEXT,
  compliance TEXT DEFAULT 'Unassessed',     -- Compliant / Non-compliant / Deviation / Unassessed
  comments TEXT,
  UNIQUE(quotation_id, line_no)
);

CREATE TABLE quote_adjustments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quotation_id TEXT NOT NULL REFERENCES quotations(id),
  package_id TEXT,
  adj_type TEXT NOT NULL,                -- delivery / unloading / tax / fx / missing_item / quantity / other
  description TEXT,
  amount TEXT NOT NULL,
  basis TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT
);

CREATE TABLE quote_selections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  package_id TEXT NOT NULL REFERENCES procurement_packages(id),
  quotation_id TEXT NOT NULL REFERENCES quotations(id),
  justification TEXT,
  not_lowest_reason TEXT,
  value_sar TEXT,
  required_role TEXT,
  status TEXT NOT NULL DEFAULT 'Pending Review',
  proposed_by TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  decided_by TEXT,
  decided_at TEXT,
  published_at TEXT
);
