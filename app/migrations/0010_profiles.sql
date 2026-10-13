-- 0010: client / owner compliance profiles. A profile is a LIST OF REQUIREMENTS loaded from the owner's own controlled documents, each with a source
-- reference. The software ships no profile content; it evaluates facts against the requirements a person loaded and approved.
CREATE TABLE client_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  name TEXT NOT NULL,
  client TEXT,
  status TEXT NOT NULL DEFAULT 'Draft',
  source_documents_json TEXT,              -- [{doc_id,title,revision,issuer,received}]
  notes TEXT,
  created_by TEXT,
  created_at TEXT,
  approved_by TEXT,
  approved_at TEXT,
  UNIQUE(code, version)
);

CREATE TABLE profile_requirements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES client_profiles(id),
  req_id TEXT NOT NULL,
  category TEXT NOT NULL,                  -- form / template / code_list / rule / procedure / deliverable / other
  title TEXT NOT NULL,
  source_ref TEXT NOT NULL,                -- controlled document id + revision + clause
  mandatory INTEGER NOT NULL DEFAULT 1,
  check_json TEXT,                         -- NULL = manual attestation ; else {fact, op, value}
  UNIQUE(profile_id, req_id)
);

CREATE TABLE project_profiles (
  project_id TEXT PRIMARY KEY REFERENCES projects(id),
  profile_code TEXT NOT NULL,
  profile_version INTEGER NOT NULL,
  linked_by TEXT,
  linked_at TEXT
);

CREATE TABLE profile_assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  profile_id INTEGER NOT NULL REFERENCES client_profiles(id),
  req_id TEXT NOT NULL,
  status TEXT NOT NULL,                    -- Met / Not met / Not applicable
  evidence TEXT NOT NULL,
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL
);
CREATE INDEX ix_profile_assess ON profile_assessments(project_id, profile_id, req_id);
