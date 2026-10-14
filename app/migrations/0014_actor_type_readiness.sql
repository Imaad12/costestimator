-- 0014: durable actor classification and export readiness.
-- users.actor_type: 'human' (a real, accountable person) | 'test' (software-validation principal; can never satisfy a production approval) | 'ai'.
-- approvals.actor_type is resolved from the users table AT RECORD TIME (never from a display name): 'human' | 'test' | 'ai' | 'unregistered' (no such user)
-- | 'inactive' | 'role_mismatch'. Pre-existing approvals are 'unregistered' (their provenance cannot be proven) and therefore never count towards production readiness.
ALTER TABLE users ADD COLUMN actor_type TEXT NOT NULL DEFAULT 'human' CHECK (actor_type IN ('human','test','ai'));
UPDATE users SET actor_type='ai' WHERE is_ai=1;
ALTER TABLE approvals ADD COLUMN actor_type TEXT NOT NULL DEFAULT 'unregistered';
ALTER TABLE approvals ADD COLUMN environment TEXT;
ALTER TABLE recon_exceptions ADD COLUMN accepted_actor_type TEXT NOT NULL DEFAULT 'unregistered';
ALTER TABLE recon_exceptions ADD COLUMN environment TEXT;
ALTER TABLE exports ADD COLUMN readiness TEXT;          -- 'production' | 'demonstration' | 'preliminary'
ALTER TABLE exports ADD COLUMN readiness_json TEXT;     -- the structured readiness evaluation that justified the label

-- 0014 (indirect eligibility): explicit eligible direct-cost base for a percentage indirect (JSON {default, rules}); NULL = legacy whole-direct-cost base, reported as unspecified.
ALTER TABLE indirect_items ADD COLUMN eligibility_json TEXT;
