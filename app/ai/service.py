"""AI-assisted proposals. EVERY output is stored as an `ai_suggestions` row with status 'Pending Review'.

Hard rules (enforced structurally + by tests/approvals/test_ai_boundary.py):
* this package never imports the approvals engine nor any service that mutates approved/estimating data;
* it can only INSERT review-pending suggestion rows (and audit entries);
* acceptance of a suggestion is performed by a human through app.services.suggestions.
"""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter

from ..core.money import to_text
from ..core.timeutil import now_iso
from ..core.units import registry
from ..database import Database, rows_to_dicts
from . import provider as prov
from .schemas import SCHEMAS

AI_ACTOR = "ai-assistant"
MAX_DOC_CHARS = 60_000


def _sanitize(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text or "")
    text = text.replace("</data>", "< /data>").replace("</document>", "< /document>")
    return text[:MAX_DOC_CHARS]


def _store(db: Database, kind: str, project_id: str | None, subject_type: str | None, subject_id: str | None, payload: dict,
           produced_by: str, confidence: str | None, source_refs: list[str] | None = None) -> int:
    sid = db.insert("ai_suggestions", dict(project_id=project_id, kind=kind, subject_type=subject_type, subject_id=subject_id,
                                           payload_json=payload, source_refs=json.dumps(source_refs or []), confidence=confidence,
                                           produced_by=produced_by, status="Pending Review", created_at=now_iso()))
    # audit entry (hash-chained) - imported lazily to keep this package free of any approvals dependency
    from ..services import audit
    audit.log(db, AI_ACTOR, "ai_suggestion", sid, f"propose:{kind}", after={"kind": kind, "by": produced_by}, project_id=project_id)
    return sid


# ----------------------------------------------------------------------------- deterministic (no AI needed)
_STOP = {"the", "and", "for", "with", "of", "to", "in", "on", "a", "an", "supply", "install", "installation", "including", "incl", "complete",
         "all", "as", "per", "etc", "type", "work", "works", "provide", "fix", "fixing"}


def _tokens(text: str) -> Counter:
    return Counter(t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if t not in _STOP)


def heuristic_mapping(db: Database, project_id: str, top_n: int = 3, min_score: float = 0.25) -> int:
    """Keyword-overlap suggestions of approved assemblies for UNMAPPED items. Labelled 'heuristic'; never auto-applied."""
    reg = registry(db)
    assemblies = rows_to_dicts(db.all("SELECT code, description, unit, cost_code FROM assemblies WHERE status='Approved' AND (project_id IS NULL OR project_id=?)",
                                      (project_id,)))
    atok = {a["code"]: _tokens(a["description"] + " " + (a["cost_code"] or "")) for a in assemblies}
    n = 0
    for it in db.all("SELECT * FROM boq_items WHERE project_id=? AND item_type='item' AND mapping_status='Unmapped'", (project_id,)):
        t = _tokens(it["description"])
        if not t:
            continue
        scored = []
        for a in assemblies:
            if it["unit"] and not reg.can_convert(it["unit"], a["unit"]):
                continue
            inter = sum((t & atok[a["code"]]).values())
            union = sum((t | atok[a["code"]]).values()) or 1
            score = inter / union
            if score >= min_score:
                scored.append((score, a))
        for score, a in sorted(scored, key=lambda x: -x[0])[:top_n]:
            _store(db, "mapping", project_id, "boq_item", it["item_key"],
                   {"item_key": it["item_key"], "assembly_code": a["code"], "confidence": "High" if score > 0.6 else ("Medium" if score > 0.4 else "Low"),
                    "rationale": f"Keyword overlap {score:.2f} between BOQ description and assembly '{a['description'][:60]}'; units compatible."},
                   "heuristic", "Medium" if score > 0.4 else "Low", [f"boq:{it['item_key']}", f"assembly:{a['code']}"])
            n += 1
    return n


def find_historical(db: Database, text: str, exclude_project: str | None = None, limit: int = 10) -> list[dict]:
    """Similar BOQ items in OTHER projects (no AI). Returns descriptions, units and the cost of any priced estimate version item."""
    t = _tokens(text)
    out = []
    for r in db.all("SELECT project_id, item_key, description, unit, quantity, assembly_code FROM boq_items WHERE item_type='item'"
                    + (" AND project_id<>?" if exclude_project else ""), (exclude_project,) if exclude_project else ()):
        c = _tokens(r["description"])
        inter = sum((t & c).values())
        if inter:
            out.append((inter / (sum((t | c).values()) or 1), dict(r)))
    return [dict(score=round(s, 3), **r) for s, r in sorted(out, key=lambda x: -x[0])[:limit]]


def spec_diff(a: str, b: str) -> list[str]:
    """Highlight specification differences between two texts (e.g. RFQ spec vs quoted spec). Deterministic."""
    sa, sb = re.split(r"(?<=[.;\n])\s+", a or ""), re.split(r"(?<=[.;\n])\s+", b or "")
    return [l for l in difflib.unified_diff(sa, sb, "specified", "quoted", lineterm="", n=0) if l and l[0] in "+-" and not l.startswith(("+++", "---"))]


def deterministic_scope_checks(db: Database, project_id: str) -> int:
    """Rule-based omissions/contradictions (no AI): e.g. items without spec/drawing refs, same description with different units."""
    n = 0
    seen: dict[str, tuple[str, str]] = {}
    for it in db.all("SELECT * FROM boq_items WHERE project_id=? AND item_type='item'", (project_id,)):
        key = re.sub(r"\W+", " ", (it["description"] or "").lower()).strip()
        if key in seen and seen[key][0] != it["unit"]:
            _store(db, "scope_gap", project_id, "boq_item", it["item_key"],
                   {"description": f"Items {seen[key][1]} and {it['item_key']} have the same description but different units ({seen[key][0]} vs {it['unit']}).",
                    "kind": "contradiction", "related_items": [seen[key][1], it["item_key"]], "confidence": "Medium", "source_refs": []},
                   "heuristic", "Medium")
            n += 1
        seen.setdefault(key, (it["unit"], it["item_key"]))
        if not it["spec_ref"] and not it["drawing_ref"]:
            _store(db, "clarifications", project_id, "boq_item", it["item_key"],
                   {"question": f"BOQ item {it['item_key']} ('{(it['description'] or '')[:80]}') has no drawing or specification reference. Please confirm the governing reference.",
                    "boq_item_key": it["item_key"], "reason": "Missing drawing/specification reference", "confidence": "Medium", "source_refs": [f"boq:{it['item_key']}"]},
                   "heuristic", "Medium")
            n += 1
    return n


# ----------------------------------------------------------------------------- AI tasks
def _run(db: Database, kind: str, task: str, instructions: str, data: str, project_id: str | None, subject_type: str | None = None,
         subject_id: str | None = None, source_refs: list[str] | None = None) -> list[int]:
    provider = prov.get_provider()
    parsed, meta = provider.complete_json(task, instructions, _sanitize(data), SCHEMAS[kind])
    payload = parsed.model_dump()
    ids: list[int] = []
    if kind == "mapping":
        for s in payload["suggestions"]:
            ids.append(_store(db, "mapping", project_id, "boq_item", s["item_key"], s, provider.name, s["confidence"], s["source_refs"]))
    elif kind == "clarifications":
        for d in payload["drafts"]:
            ids.append(_store(db, "clarifications", project_id, "boq_item", d.get("boq_item_key"), d, provider.name, d["confidence"], d["source_refs"]))
    elif kind == "scope_gaps":
        for g in payload["gaps"]:
            ids.append(_store(db, "scope_gap", project_id, "boq_item", None, g, provider.name, g["confidence"], g["source_refs"]))
    else:
        ids.append(_store(db, kind, project_id, subject_type, subject_id, {**payload, "_meta": meta}, provider.name,
                          payload.get("confidence"), source_refs))
    return ids


def ai_suggest_mappings(db: Database, project_id: str) -> list[int]:
    items = rows_to_dicts(db.all("SELECT item_key, description, unit, spec_ref FROM boq_items WHERE project_id=? AND item_type='item' AND mapping_status='Unmapped' LIMIT 80", (project_id,)))
    asm = rows_to_dicts(db.all("SELECT code, description, unit FROM assemblies WHERE status='Approved' AND (project_id IS NULL OR project_id=?)", (project_id,)))
    data = json.dumps({"boq_items": items, "approved_assemblies": asm}, ensure_ascii=False)
    return _run(db, "mapping", "Suggest approved-assembly mappings for BOQ items",
                "Only use assembly codes from approved_assemblies and item keys from boq_items. Units must be compatible. Max one suggestion per item.",
                data, project_id)


def ai_extract_quotation(db: Database, project_id: str | None, document_text: str, source_name: str = "uploaded document") -> list[int]:
    return _run(db, "quote_extraction", "Extract supplier quotation fields",
                "Extract only values present in the document. Quote the supporting text verbatim in evidence_quote. Do not infer prices or tax treatment that are not stated.",
                f"<document name={json.dumps(source_name)}>\n{document_text}\n</document>", project_id, "document", source_name, [f"doc:{source_name}"])


def ai_draft_clarifications(db: Database, project_id: str, context_text: str) -> list[int]:
    return _run(db, "clarifications", "Draft client clarification questions",
                "Identify ambiguities, omissions or contradictions in the supplied tender text/BOQ extract. Cite BOQ item keys or document locations in source_refs.",
                context_text, project_id)


def ai_suggest_scope_gaps(db: Database, project_id: str, context_text: str) -> list[int]:
    return _run(db, "scope_gaps", "Suggest possible scope gaps or contradictions", "Only report issues evidenced by the supplied text.", context_text, project_id)


def ai_draft_rfq_email(db: Database, project_id: str, rfq_id: str, rfq_body: str) -> list[int]:
    return _run(db, "rfq_email", "Polish an RFQ email draft", "Keep all quantities, units and requirements unchanged. Do not add contacts or prices.",
                rfq_body, project_id, "rfq", rfq_id)


def ai_summarise_exclusions(db: Database, quotation_id: str, quote_text: str) -> list[int]:
    return _run(db, "exclusion_summary", "Summarise supplier exclusions and deviations", "List only what the text states.", quote_text, None,
                "quotation", quotation_id)
