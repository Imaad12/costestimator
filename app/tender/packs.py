"""Tender / handover pack generation, manifest, approvals and the pack validator.

A pack is generated from ONE frozen estimate version and the registers; every document is rendered in DOCX and PDF (and XLSX for tabular records), registered in
`generated_documents` with template id/version, revision, status and checksum, and described by manifest.json. Regeneration with identical inputs and template version
yields byte-identical files. The pack classification and every document status come from services/readiness - a document never says 'approved' or 'submission ready'
unless the application gate verified it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..approvals import engine as approvals
from ..core.errors import AppError, Conflict, ValidationFailed
from ..core.timeutil import now_iso
from ..database import Database, rows_to_dicts
from ..models.actor import Actor
from ..models.enums import Entity
from ..services import audit, estimates, projects, readiness, tender
from . import builders, catalogue, handover, model
from .catalogue import COND, MCR, NA, REQ, TEMPLATE_VERSION

CONFIDENTIAL_REAL = "CONFIDENTIAL - commercial and technical tender information"
CONFIDENTIAL_SYN = "CONFIDENTIAL (synthetic test data) - no real customer or supplier data"
SYN_MARK = "SYNTHETIC TEST DATA - FICTIONAL CUSTOMER - NOT A REAL TENDER - NOT A MARKET QUOTE - NOT FOR SUBMISSION"
HYPO_BANNER = "HYPOTHETICAL POST-AWARD HANDOVER - SIMULATION ONLY - NO AWARD HAS BEEN MADE"


def latest_version_id(db: Database, project_id: str) -> int:
    r = db.one("SELECT id FROM estimate_versions WHERE project_id=? ORDER BY version_no DESC LIMIT 1", (project_id,))
    if not r:
        raise ValidationFailed("Freeze an estimate version before generating a pack.", code="NO_FROZEN_VERSION")
    return r["id"]


def _export_approval(db: Database, project_id: str, version_id: int):
    v = estimates.get_version(db, version_id)
    r = db.one("SELECT id FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' ORDER BY id DESC LIMIT 1", (Entity.TENDER_EXPORT.value, f"{project_id}/v{v['version_no']}"))
    return r["id"] if r else None


def doc_status(classification: str, production_ready: bool, blocked: bool, approved: bool) -> str:
    if blocked:
        return "BLOCKED"
    if production_ready:
        return "Approved for Submission" if approved else "For Review"
    return "Preliminary (DEMONSTRATION)" if classification == "demonstration" else "Draft"


def _doc_approved(db: Database, project_id: str, doc_id: str) -> bool:
    row = db.one("SELECT * FROM approvals WHERE entity_type=? AND entity_id=? AND action='approve' ORDER BY id DESC LIMIT 1", (Entity.TENDER_DOCUMENT.value, f"{project_id}/{doc_id}"))
    if not row:
        return False
    probs, _ = readiness.check_approval(db, row, "document approval", entity_type=Entity.TENDER_DOCUMENT.value, entity_id=f"{project_id}/{doc_id}")
    return not probs


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:48]


def _render(doc: model.Doc, meta: dict, out: Path, formats: tuple[str, ...]) -> dict:
    files = {}
    stem = f"{meta['doc_id']}_r{meta['revision']}_{_slug(doc.title)}"
    for fmt in formats:
        p = out / f"{stem}.{fmt}"
        {"docx": model.render_docx, "xlsx": model.render_xlsx, "pdf": model.render_pdf}[fmt](doc, meta, p)
        files[fmt] = dict(path=str(p.relative_to(out.parent)), sha256=model.sha256_file(p), bytes=p.stat().st_size)
    return files


def generate_pack(db: Database, actor: Actor, project_id: str, *, out_root: Path, issue_date: str, version_id: int | None = None, reviewer: str = "not yet reviewed") -> dict:
    """Generate the applicable tender documents for the project from the latest (or given) frozen estimate version."""
    approvals.require_author(actor)
    projects.require_active(db, project_id)
    vid = version_id or latest_version_id(db, project_id)
    v = estimates.get_version(db, vid)
    rev = (db.scalar("SELECT MAX(revision) FROM tender_packs WHERE project_id=? AND kind='tender'", (project_id,)) or 0) + 1
    r = readiness.evaluate(db, project_id, vid, _export_approval(db, project_id, vid))
    mx = catalogue.matrix(db, project_id)
    out = Path(out_root) / f"{project_id}_tender_pack_r{rev}"
    out.mkdir(parents=True, exist_ok=True)
    c = builders.Ctx(db, project_id, vid, issue_date=issue_date, revision=rev, readiness=r)
    proj = c.project
    # pass 1: build every applicable document's content (nothing is rendered yet) so the PACK's label can reflect BLOCKED documents and unresolved placeholders
    built: dict[int, model.Doc] = {}
    for m in mx["rows"]:
        if m["applicability"] == NA or m["n"] == 45:
            continue
        try:
            doc = builders.BUILDERS[m["n"]](c)
        except AppError as e:
            doc = model.Doc(m["code"], m["title"], [model.Section("Not produced", [model.missing(f"{e.code}: {e}")])])
        if m["applicability"] == MCR:
            doc = model.Doc(m["code"], m["title"], [model.Section("Blocked: missing customer requirement", [model.missing(m["reason"])])], facts=doc.facts, limitations=builders._lim(c))
        built[m["n"]] = doc
    cust_missing = model.MISSING in c.customer             # the customer name appears in every document's header block: without it every document carries a placeholder
    blocked_codes = sorted(f"D{n:02d}" for n, d in built.items() if d.missing_inputs() or cust_missing)
    todo_codes = sorted(f"D{n:02d}" for n, d in built.items() if "TO BE COMPLETED BY A COMPETENT PERSON" in d.all_text())
    pack_class = r["classification"]
    pack_ready = r["production_ready"] and not blocked_codes and not todo_codes
    if r["production_ready"] and not pack_ready:           # the approval chain is sound but the pack is not: it must not be described as submission-ready
        pack_class = "not_ready"
        banner = "NOT SUBMISSION READY - the approval chain verifies but the pack has " + "; ".join(x for x in (f"BLOCKED documents ({', '.join(blocked_codes)})" if blocked_codes else "",
                                                                                                           f"unresolved placeholders ({', '.join(todo_codes)})" if todo_codes else "") if x)
    else:
        banner = readiness.banner(r)
    if pack_class != r["classification"] or not pack_ready:
        extra = ([f"pack: documents BLOCKED by missing inputs ({', '.join(blocked_codes)})"] if blocked_codes else []) + ([f"pack: unresolved placeholders in {', '.join(todo_codes)}"] if todo_codes else [])
        c.readiness = {**r, "classification": pack_class, "production_ready": pack_ready, "reasons": r["reasons"] + extra}
        for n_ in (15, 43):                      # the readiness record and the handover checklist must state the PACK's status, not only the approval chain's
            if n_ in built:
                built[n_] = builders.BUILDERS[n_](c)
    pack_pk = db.insert("tender_packs", dict(project_id=project_id, kind="tender", revision=rev, estimate_version_id=vid, estimate_fingerprint=v["inputs_hash"], classification=pack_class,
                                             status_label=banner, out_dir=str(out), hypothetical=0, created_by=actor.username, created_at=now_iso()))
    docs_info: list[dict] = []
    rows = [m for m in mx["rows"] if m["n"] != 45] + [m for m in mx["rows"] if m["n"] == 45]
    for m in rows:
        n, code = m["n"], m["code"]
        doc_id = f"{project_id}-{code}"
        tmpl = f"{m['template_id']}@{TEMPLATE_VERSION}"
        info = dict(code=code, doc_id=doc_id, title=m["title"], revision=rev, applicability=m["applicability"], reason=m["reason"], template=tmpl, formats="", sha256="", status="", blocked_reason=None, files={})
        if m["applicability"] == NA:
            info["status"] = "Not Applicable"
            docs_info.append(info)
            db.insert("generated_documents", dict(pack_pk=pack_pk, doc_code=code, doc_id=doc_id, title=m["title"], template_id=m["template_id"], template_version=TEMPLATE_VERSION, revision=rev, status="Not Applicable",
                                                  applicability=NA, applicability_reason=m["reason"], created_at=now_iso()))
            continue
        if n == 45:
            c.pack_docs = [d for d in docs_info]
            doc = builders.BUILDERS[45](c)
        else:
            doc = built[n]
        miss = doc.missing_inputs() + (["customer name"] if model.MISSING in c.customer else [])
        status = doc_status(pack_class, pack_ready, bool(miss), _doc_approved(db, project_id, doc_id))
        blocked_reason = "; ".join(miss) if miss else None
        meta = dict(project_id=project_id, project_name=proj["name"], customer=c.customer, doc_id=doc_id, title=doc.title, revision=rev, issue_date=issue_date, status=status, author=actor.username,
                    reviewer=reviewer, estimate_version=f"v{v['version_no']}", fingerprint=v["inputs_hash"][:16], template=tmpl, banner=banner, synthetic_mark=SYN_MARK if c.synthetic else "",
                    confidentiality=CONFIDENTIAL_SYN if c.synthetic else CONFIDENTIAL_REAL)
        fmts = ("docx", "pdf") + (("xlsx",) if m["xlsx"] else ())
        files = _render(doc, meta, out, fmts)
        info.update(status=status, formats=",".join(fmts), sha256=files["docx"]["sha256"], blocked_reason=blocked_reason, files=files)
        docs_info.append(info)
        db.insert("generated_documents", dict(pack_pk=pack_pk, doc_code=code, doc_id=doc_id, title=doc.title, template_id=m["template_id"], template_version=TEMPLATE_VERSION, revision=rev, status=status,
                                              applicability=m["applicability"], applicability_reason=m["reason"], format=",".join(fmts), path=files["docx"]["path"], sha256=files["docx"]["sha256"],
                                              bytes=files["docx"]["bytes"], blocked_reason=blocked_reason, refs_json=json.dumps(doc.refs), facts_json=json.dumps(doc.facts, default=str), created_at=now_iso()))
    manifest = dict(project_id=project_id, kind="tender", revision=rev, issue_date=issue_date, estimate_version=v["version_no"], estimate_fingerprint=v["inputs_hash"], classification=pack_class,
                    production_ready=pack_ready, banner=banner, template_version=TEMPLATE_VERSION, reasons_not_ready=r["reasons"], blocked_documents=blocked_codes, documents_with_placeholders=todo_codes, synthetic=c.synthetic,
                    applicability_counts=mx["counts"], documents=docs_info)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str), encoding="utf-8")
    (out / "applicability_matrix.json").write_text(json.dumps(mx, indent=1, sort_keys=True, default=str), encoding="utf-8")
    db.update("tender_packs", {"manifest_sha256": model.sha256_file(out / "manifest.json")}, "pk=?", (pack_pk,))
    audit.log(db, actor, "tender_pack", f"{project_id}/tender/r{rev}", "generate", after=dict(classification=pack_class, documents=len(docs_info)), project_id=project_id)
    return dict(pack_pk=pack_pk, revision=rev, out_dir=str(out), classification=pack_class, production_ready=pack_ready, banner=banner, documents=docs_info, counts=mx["counts"], reasons=r["reasons"])


def generate_handover_pack(db: Database, actor: Actor, project_id: str, *, out_root: Path, issue_date: str, version_id: int | None = None) -> dict:
    """Hypothetical post-award handover. Refuses unless a person has recorded an explicit simulated award scenario: an award is never invented."""
    approvals.require_author(actor)
    ctx = tender.context(db, project_id)
    if str(ctx.get("award_scenario") or "") != "hypothetical":
        raise ValidationFailed("No award scenario is selected. Record tender_context.award_scenario = 'hypothetical' to generate a SIMULATED handover pack; an award is never assumed.", code="AWARD_NOT_SELECTED")
    vid = version_id or latest_version_id(db, project_id)
    v = estimates.get_version(db, vid)
    rev = (db.scalar("SELECT MAX(revision) FROM tender_packs WHERE project_id=? AND kind='handover'", (project_id,)) or 0) + 1
    r = readiness.evaluate(db, project_id, vid, _export_approval(db, project_id, vid))
    banner = HYPO_BANNER + " | " + readiness.banner(r)
    out = Path(out_root) / f"{project_id}_handover_pack_r{rev}"
    out.mkdir(parents=True, exist_ok=True)
    c = builders.Ctx(db, project_id, vid, issue_date=issue_date, revision=rev, readiness=r, hypothetical=True)
    pack_pk = db.insert("tender_packs", dict(project_id=project_id, kind="handover", revision=rev, estimate_version_id=vid, estimate_fingerprint=v["inputs_hash"], classification=r["classification"],
                                             status_label=banner, out_dir=str(out), hypothetical=1, created_by=actor.username, created_at=now_iso()))
    infos = []
    for code, title, tid in catalogue.HANDOVER_DOCS:
        doc = handover.HANDOVER[code](c)
        miss = doc.missing_inputs()
        status = "BLOCKED" if miss else "Preliminary (SIMULATED HANDOVER)"
        doc_id = f"{project_id}-{code}"
        tmpl = f"{tid}@{TEMPLATE_VERSION}"
        meta = dict(project_id=project_id, project_name=c.project["name"], customer=c.customer, doc_id=doc_id, title=doc.title, revision=rev, issue_date=issue_date, status=status, author=actor.username,
                    reviewer="not yet reviewed", estimate_version=f"v{v['version_no']}", fingerprint=v["inputs_hash"][:16], template=tmpl, banner=banner, synthetic_mark=SYN_MARK if c.synthetic else "",
                    confidentiality=CONFIDENTIAL_SYN if c.synthetic else CONFIDENTIAL_REAL)
        fmts = ("docx", "pdf") + (("xlsx",) if doc.xlsx else ())
        files = _render(doc, meta, out, fmts)
        infos.append(dict(code=code, doc_id=doc_id, title=doc.title, revision=rev, applicability=REQ, reason="simulated award scenario", template=tmpl, formats=",".join(fmts), sha256=files["docx"]["sha256"],
                          status=status, blocked_reason="; ".join(miss) or None, files=files))
        db.insert("generated_documents", dict(pack_pk=pack_pk, doc_code=code, doc_id=doc_id, title=doc.title, template_id=tid, template_version=TEMPLATE_VERSION, revision=rev, status=status, applicability=REQ,
                                              applicability_reason="simulated award scenario", format=",".join(fmts), path=files["docx"]["path"], sha256=files["docx"]["sha256"], bytes=files["docx"]["bytes"],
                                              blocked_reason="; ".join(miss) or None, refs_json=json.dumps(doc.refs), facts_json=json.dumps(doc.facts, default=str), created_at=now_iso()))
    manifest = dict(project_id=project_id, kind="handover", hypothetical=True, revision=rev, issue_date=issue_date, estimate_version=v["version_no"], estimate_fingerprint=v["inputs_hash"], classification=r["classification"],
                    banner=banner, template_version=TEMPLATE_VERSION, documents=infos)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str), encoding="utf-8")
    db.update("tender_packs", {"manifest_sha256": model.sha256_file(out / "manifest.json")}, "pk=?", (pack_pk,))
    audit.log(db, actor, "tender_pack", f"{project_id}/handover/r{rev}", "generate", after=dict(hypothetical=True, documents=len(infos)), project_id=project_id)
    return dict(pack_pk=pack_pk, revision=rev, out_dir=str(out), banner=banner, documents=infos)


def approve_document(db: Database, actor: Actor, project_id: str, doc_id: str, comments: str | None = None) -> int:
    """A person approves one generated document (e.g. the technical or commercial proposal). On a real project this needs a registered human user in production."""
    authorize_doc = approvals.authorize
    authorize_doc(actor, Entity.TENDER_DOCUMENT.value, "approve")
    approvals.require_production_actor(db, actor, project_id, "document approval")
    if not db.one("SELECT 1 FROM generated_documents g JOIN tender_packs p ON p.pk=g.pack_pk WHERE p.project_id=? AND g.doc_id=?", (project_id, doc_id)):
        raise ValidationFailed(f"Document {doc_id} is not in any generated pack.", code="DOC_NOT_FOUND")
    last = db.one("SELECT g.status, g.revision FROM generated_documents g JOIN tender_packs p ON p.pk=g.pack_pk WHERE p.project_id=? AND g.doc_id=? ORDER BY g.pk DESC LIMIT 1", (project_id, doc_id))
    if last["status"] == "BLOCKED":
        raise Conflict("A BLOCKED document cannot be approved until its missing input is resolved.", code="DOC_BLOCKED")
    return approvals.record(db, actor, Entity.TENDER_DOCUMENT.value, f"{project_id}/{doc_id}", "approve", project_id=project_id, version=last["revision"], comments=comments)


# ================================================================================================ validator
BANNED = [(re.compile(r"submission[- ]ready", re.I), "claims submission readiness"), (re.compile(r"approved for submission", re.I), "claims approval for submission"),
          (re.compile(r"\bcompliant\b", re.I), "claims compliance")]


def _claims(text: str) -> list[str]:
    out = []
    for rx, what in BANNED:
        for m in rx.finditer(text):
            pre = text[max(0, m.start() - 4):m.start()].lower()
            if pre.endswith("not ") or pre.endswith("non-") or pre.endswith("non "):
                continue
            out.append(what)
            break
    return out


def validate_pack(db: Database, pack_pk: int, root: Path | None = None) -> dict:
    """Check a generated pack: presence vs applicability, files parse with an independent reader, checksums, revision/estimate consistency, cross-references, arithmetic,
    unresolved placeholders and unsupported approval claims."""
    p = db.one("SELECT * FROM tender_packs WHERE pk=?", (pack_pk,))
    if not p:
        raise ValidationFailed("Pack not found.", code="PACK_NOT_FOUND")
    p = dict(p)
    out = Path(p["out_dir"])
    rows = rows_to_dicts(db.all("SELECT * FROM generated_documents WHERE pack_pk=? ORDER BY doc_code", (pack_pk,)))
    errors, warns = [], []
    ids = {r["doc_id"] for r in rows}
    if p["kind"] == "tender":
        expected = {f"D{n:02d}" for n, *_ in catalogue.CATALOGUE}
        got = {r["doc_code"] for r in rows}
        for m in sorted(expected - got):
            errors.append(f"{m}: not in the applicability matrix / pack")
    manifest = json.loads((out / "manifest.json").read_text())
    by_code = {d["code"]: d for d in manifest["documents"]}
    facts_seen: dict[str, dict] = {}
    todo_docs = 0
    for r in rows:
        if r["status"] == "Not Applicable":
            if not r["applicability_reason"]:
                errors.append(f"{r['doc_code']}: Not Applicable without a reason")
            continue
        if r["revision"] != p["revision"]:
            errors.append(f"{r['doc_code']}: revision {r['revision']} differs from pack revision {p['revision']}")
        if not r["template_version"] or not r["template_id"]:
            errors.append(f"{r['doc_code']}: template id/version not recorded")
        files = by_code.get(r["doc_code"], {}).get("files", {})
        if not files:
            errors.append(f"{r['doc_code']}: no files in manifest")
        for fmt, f in files.items():
            fp = out.parent / f["path"]
            if not fp.exists():
                errors.append(f"{r['doc_code']}: {fmt} file missing")
                continue
            if model.sha256_file(fp) != f["sha256"]:
                errors.append(f"{r['doc_code']}: {fmt} checksum differs from manifest")
            try:
                txt = model.parse_back(fp)["text"]
            except Exception as e:                                   # noqa: BLE001 - any reader failure = invalid document
                errors.append(f"{r['doc_code']}: {fmt} does not open as a genuine {fmt.upper()} ({e})")
                continue
            if r["doc_id"] not in txt and fmt != "xlsx":
                errors.append(f"{r['doc_code']}: {fmt} does not carry its document id")
            if fmt == "docx":
                if "[[MISSING" in txt and r["status"] != "BLOCKED":
                    errors.append(f"{r['doc_code']}: unresolved placeholder in a document not marked BLOCKED")
                if "TO BE COMPLETED BY A COMPETENT PERSON" in txt:
                    todo_docs += 1
                    (errors if p["classification"] == "production" else warns).append(f"{r['doc_code']}: contains 'TO BE COMPLETED' placeholders")
                if p["classification"] != "production":
                    for cl in _claims(txt):
                        errors.append(f"{r['doc_code']}: text {cl} but the application gate classification is '{p['classification']}'")
                elif r["status"] != "Approved for Submission":
                    pass
        fj = json.loads(r["facts_json"] or "{}")
        for k, val in fj.items():
            facts_seen.setdefault(k, {})[r["doc_code"]] = str(val)
        for ref in json.loads(r["refs_json"] or "[]"):
            if ref not in ids and not any(ref.endswith(x) for x in ids):
                errors.append(f"{r['doc_code']}: stale reference {ref}")
    for k, m in facts_seen.items():
        if len(set(m.values())) > 1:
            errors.append(f"inconsistent value '{k}' across documents: {dict(sorted(m.items()))}")
    fx = {k: next(iter(m.values())) for k, m in facts_seen.items()}
    try:
        from decimal import Decimal as D
        if all(k in fx and fx[k] not in ("None", "") for k in ("schedule_total", "vat", "payable")) and abs(D(fx["schedule_total"]) + D(fx["vat"]) - D(fx["payable"])) > D("0.011"):
            errors.append(f"arithmetic: tendered schedule total {fx['schedule_total']} + VAT {fx['vat']} != payable {fx['payable']}")
        if "net_price" in fx and "schedule_total" in fx and fx["net_price"] not in ("None", "") and abs(D(fx["schedule_total"]) - D(fx["net_price"])) > D("500"):
            errors.append(f"arithmetic: tendered schedule total {fx['schedule_total']} differs from the commercial net price {fx['net_price']} by more than the rounding allowance")
    except Exception as e:                                           # noqa: BLE001
        errors.append(f"arithmetic check could not run: {e}")
    v = db.one("SELECT inputs_hash FROM estimate_versions WHERE id=?", (p["estimate_version_id"],))
    if v and v["inputs_hash"] != p["estimate_fingerprint"]:
        errors.append("pack estimate fingerprint differs from the frozen version")
    blocked = [r["doc_code"] for r in rows if r["status"] == "BLOCKED"]
    return dict(pack_pk=pack_pk, ok=not errors, errors=errors, warnings=warns, blocked_documents=blocked, documents=len(rows), files_checked=sum(len(by_code.get(r["doc_code"], {}).get("files", {})) for r in rows),
                classification=p["classification"], facts_checked=sorted(facts_seen))
