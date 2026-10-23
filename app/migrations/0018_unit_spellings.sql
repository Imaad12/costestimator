-- Spellings seen in real BOQs: PSC (a common typo of PCS) = number, LOT = lump sum. Reference data only (spelling -> existing canonical unit); no unit is added or redefined.
UPDATE units SET synonyms = synonyms || '|psc' WHERE code = 'nr' AND '|' || synonyms || '|' NOT LIKE '%|psc|%';
UPDATE units SET synonyms = synonyms || '|lot' WHERE code = 'ls' AND '|' || synonyms || '|' NOT LIKE '%|lot|%';
