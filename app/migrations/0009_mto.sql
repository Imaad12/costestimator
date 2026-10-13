-- 0009: material take-off derivation records. Derived takeoff lines are marked (origin) and need a human pricing decision before use.
ALTER TABLE takeoff_resource_lines ADD COLUMN origin TEXT;        -- NULL = imported/pre-calculated by the estimator ; 'mto' = derived by a template application
ALTER TABLE takeoff_resource_lines ADD COLUMN origin_ref TEXT;    -- template code for 'mto'

CREATE TABLE mto_applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  item_key TEXT NOT NULL,
  template TEXT NOT NULL,
  driver_qty TEXT NOT NULL,
  driver_unit TEXT NOT NULL,
  driver_source TEXT,                      -- where the human-measured driver quantity comes from (MTO / drawing / register reference)
  factor_refs_json TEXT NOT NULL,          -- [{slot, param_id, code, version, factor, resource_id}]
  skipped_json TEXT,                       -- slots the estimator explicitly excluded
  lines_json TEXT NOT NULL,
  applied_by TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
CREATE INDEX ix_mto_app ON mto_applications(project_id, item_key, template);
