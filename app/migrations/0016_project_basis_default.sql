-- Project region/currency: record when they are the system defaults (KSA-ALL / SAR) rather than values a person chose or confirmed.
-- Existing projects are left as they are (0 = not flagged). The flag is cleared by projects.confirm_basis (audited).
ALTER TABLE projects ADD COLUMN basis_defaulted INTEGER NOT NULL DEFAULT 0;
