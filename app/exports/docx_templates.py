"""Creates the .docx templates shipped in templates/ (run via scripts/generate_templates.py)."""
from __future__ import annotations

from pathlib import Path

from .docx_util import build_simple_template

OFFER_LINES = [
    "{{status_banner}}",
    "Date: {{date}}",
    "Our ref: {{offer_ref}}        Tender ref: {{tender_ref}}",
    "To: {{client}}",
    "Project: {{project_name}} - {{location}}",
    "Subject: Offer for {{project_name}}",
    "We, {{company_name}} ({{company_address}}; CR {{cr_number}}; VAT {{vat_number}}), are pleased to submit our offer for the above project "
    "in accordance with the tender documents and the pricing schedule attached, subject to the inclusions, exclusions, qualifications "
    "and clarifications stated below.",
    "Offer price (before tax): SAR {{total_pre_tax}}",
    "{{tax_lines}}",
    "Offer price (including tax): SAR {{total_incl_tax}}",
    "This offer is valid for {{validity_days}} days from the date of this letter. Payment terms: {{payment_terms}}.",
    "Pricing basis: {{pricing_basis}}",
    "INCLUSIONS",
    "{{INCLUSIONS}}",
    "EXCLUSIONS",
    "{{EXCLUSIONS}}",
    "QUALIFICATIONS",
    "{{QUALIFICATIONS}}",
    "CLARIFICATIONS AND ASSUMPTIONS ON WHICH THE OFFER IS BASED",
    "{{CLARIFICATIONS}}",
    "Yours faithfully,",
    "{{signatory}}",
    "{{company_name}}",
    "This document is a draft prepared by an estimating tool for human review. It is not legal advice and does not constitute a "
    "binding commitment until reviewed and signed by an authorised signatory.",
]
REPORT_LINES = [
    "{{status_banner}}",
    "Project: {{project_name}} ({{project_id}})        Client: {{client}}",
    "Estimate version: {{version}}        Prepared: {{date}}        Estimate state: {{state}}",
    "SUMMARY",
    "{{SUMMARY}}",
    "COST RECONCILIATION (resource level to selling price)",
    "{{RECON_TABLE}}",
    "EXCEPTIONS AND OPEN ISSUES",
    "{{EXCEPTIONS}}",
    "ASSUMPTIONS IN USE",
    "{{ASSUMPTIONS}}",
    "This report is generated from deterministic calculations; all inputs remain subject to human approval.",
]


def generate_docx_templates(out_dir: Path) -> list[Path]:
    paths = [out_dir / "letter_of_offer_template.docx", out_dir / "estimate_report_template.docx"]
    build_simple_template(paths[0], "LETTER OF OFFER", OFFER_LINES, "{{company_name}}")
    build_simple_template(paths[1], "ESTIMATE REPORT", REPORT_LINES, "KSA Construction Estimating Suite")
    return paths
