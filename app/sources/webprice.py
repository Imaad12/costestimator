"""Evidence extraction from a public supplier/manufacturer page: product, spec, unit, currency, price, VAT/delivery basis.

Deliberately NOT a site-specific scraper.  It reads only machine-readable markup that sites publish for this purpose (schema.org
JSON-LD, microdata `itemprop`, OpenGraph product tags) plus an explicit, low-confidence text-pattern fallback.  Every candidate
carries the snippet it was read from.  If a page gives a specification but no price, a *specification-only* candidate is returned
and NO price is inferred.  Nothing is stored here; `rate_updates.candidates` validates and queues the output for human review.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

SAR_TOKENS = {"SAR", "SR", "SAR.", "ر.س", "ريال", "ريال سعودي", "﷼"}
QUOTE_PHRASES = re.compile(r"request (a )?(quote|quotation|price)|call (us )?for (price|quote)|price on (request|application)|contact (us )?for (price|pricing)|"
                           r"get (a )?quote|اطلب\s*(عرض)?\s*سعر|السعر عند الطلب|تواصل للحصول", re.I)
VAT_INC = re.compile(r"incl(?:ude[sd]?|uding|usive)?\.?\s*(of\s*)?(vat|tax)|\bvat\s*(included|inclusive)|with\s*vat|شامل\s*(ضريبة|الضريبة)", re.I)
VAT_EXC = re.compile(r"excl(?:ude[sd]?|uding|usive)?\.?\s*(of\s*)?(vat|tax)|\bex\.?\s*-?vat|\+\s*vat|before\s*vat|vat\s*(excluded|extra|not included)|غير\s*شامل", re.I)
DELIVERED = re.compile(r"(free |fast |nationwide )?deliver(y|ed)( included| to site)?|shipping included|توصيل", re.I)
DELIVERY_EXCLUDED = re.compile(r"ex[- ]?works|collection only|pick[- ]?up|delivery (extra|not included|charges apply)|shipping (extra|calculated at checkout)", re.I)
INSTALL_INC = re.compile(r"supply (and|&) install|installation included|installed price|inc(?:l)?\.? installation|تركيب", re.I)
SALE = re.compile(r"\bsale\b|\bpromo|discount|\bwas\b|\bnow\b|% ?off|special offer|عرض خاص|تخفيض", re.I)
SAUDI = re.compile(r"saudi|\bksa\b|riyadh|jeddah|dammam|khobar|makkah|madinah|المملكة|السعودية|الرياض|جدة|الدمام", re.I)
PRICE_TEXT = re.compile(r"(?P<cur>SAR|SR|ر\.س|﷼)\s*(?P<a>\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,4})?|\d+(?:\.\d{1,4})?)|"
                        r"(?P<b>\d{1,3}(?:,\d{3})*(?:\.\d{1,4})?|\d+(?:\.\d{1,4})?)\s*(?P<cur2>SAR|SR|ر\.س|﷼)", re.I)
UNIT_TEXT = re.compile(r"(?:per|/|each|a|لكل)\s*(m2|m²|sqm|sq\.? ?m|m3|m³|lm|m\b|meter|metre|kg|ton|tonne|bag|piece|pc|pcs|nr|no|set|roll|sheet|ea|each|litre|liter|l\b)", re.I)


@dataclass
class RawCandidate:
    name: str | None = None
    sku: str | None = None
    brand: str | None = None
    specification: str | None = None
    price: str | None = None                    # exactly as published (digits and '.'), never converted
    currency: str | None = None
    unit_text: str | None = None
    availability: str | None = None
    price_valid_until: str | None = None
    method: str = ""
    snippet: str = ""
    flags: list[str] = field(default_factory=list)
    price_kind: str = "Unknown"
    tax_basis: str = "Unknown"
    delivery_basis: str = "Unknown"
    installation_included: str = "Unknown"
    geography: str = "Unknown"
    page_date: str | None = None
    effective_date: str | None = None


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.ld: list[str] = []
        self.micro: list[dict[str, str]] = []
        self.text: list[str] = []
        self.struck: list[str] = []
        self._in = []
        self._ld = False
        self._ld_buf = ""
        self._scope: dict[str, str] | None = None
        self._struck = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._in.append(tag)
        if tag == "title":
            self._cap = "title"
        if tag == "meta":
            k = a.get("property") or a.get("name") or a.get("itemprop")
            if k and a.get("content") is not None:
                self.meta[k.lower()] = a["content"]
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._ld, self._ld_buf = True, ""
        if "itemscope" in a and "product" in (a.get("itemtype") or "").lower():
            self._scope = {}
            self.micro.append(self._scope)
        ip = a.get("itemprop")
        if ip and self._scope is not None:
            val = a.get("content") or a.get("value")
            if val is not None:
                self._scope[ip.lower()] = val
            else:
                self._pending_prop = ip.lower()
        if tag in ("del", "s", "strike"):
            self._struck = True

    def handle_endtag(self, tag):
        if self._in and self._in[-1] == tag:
            self._in.pop()
        if tag == "script" and self._ld:
            self.ld.append(self._ld_buf)
            self._ld = False
        if tag in ("del", "s", "strike"):
            self._struck = False
        self._cap = None
        self._pending_prop = None

    _cap = None
    _pending_prop = None

    def handle_data(self, data):
        if self._ld:
            self._ld_buf += data
            return
        if "script" in self._in or "style" in self._in:
            return
        t = data.strip()
        if not t:
            return
        if self._cap == "title":
            self.title += t
        if self._pending_prop and self._scope is not None:
            self._scope.setdefault(self._pending_prop, t)
        self.text.append(t)
        if self._struck:
            self.struck.append(t)


def _clean_price(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().replace(" ", " ")
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return format(d, "f") if d > 0 else None


def _walk_ld(node: Any):
    if isinstance(node, list):
        for n in node:
            yield from _walk_ld(n)
    elif isinstance(node, dict):
        yield node
        for k in ("@graph", "itemListElement", "offers", "hasVariant", "isRelatedTo"):
            if k in node:
                yield from _walk_ld(node[k])


def _norm_currency(c: str | None) -> str | None:
    if not c:
        return None
    c = c.strip()
    return "SAR" if c in SAR_TOKENS or c.upper() in SAR_TOKENS else c.upper()


def extract_candidates(html: str, url: str, *, retrieved_on: date, max_age_days: int = 365) -> list[RawCandidate]:
    pg = _Page()
    try:
        pg.feed(html)
    except Exception:  # malformed markup should not crash a refresh
        pass
    text = " ".join(pg.text)
    host = urlsplit(url).hostname or ""
    page_date = pg.meta.get("article:modified_time") or pg.meta.get("article:published_time") or pg.meta.get("datemodified") or pg.meta.get("datepublished")
    out: list[RawCandidate] = []

    # 1) schema.org JSON-LD
    for blob in pg.ld:
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        for node in _walk_ld(data):
            types = node.get("@type")
            types = [types] if isinstance(types, str) else (types or [])
            if "Product" not in types:
                continue
            offers = node.get("offers")
            offer_list = [o for o in (offers if isinstance(offers, list) else [offers]) if isinstance(o, dict)] or [{}]
            for o in offer_list:
                ps = o.get("priceSpecification") if isinstance(o.get("priceSpecification"), dict) else {}
                price = o.get("price") or ps.get("price")
                flags = []
                if o.get("@type") == "AggregateOffer" or (o.get("lowPrice") and not price):
                    price = o.get("lowPrice")
                    flags.append("PRICE_RANGE")
                c = RawCandidate(name=node.get("name"), sku=str(node.get("sku") or node.get("mpn") or "") or None,
                                 brand=(node.get("brand", {}).get("name") if isinstance(node.get("brand"), dict) else node.get("brand")),
                                 specification=str(node.get("description") or "")[:600] or None, price=_clean_price(price),
                                 currency=_norm_currency(o.get("priceCurrency")), availability=str(o.get("availability") or "").rsplit("/", 1)[-1] or None,
                                 price_valid_until=o.get("priceValidUntil"), method="JSON-LD schema.org Product/Offer", flags=flags,
                                 snippet=json.dumps({k: node.get(k) for k in ("name", "sku", "description")}, ensure_ascii=False)[:300]
                                 + " | offer=" + json.dumps({k: o.get(k) for k in ("price", "priceCurrency", "priceValidUntil", "availability")}, ensure_ascii=False))
                if ps.get("valueAddedTaxIncluded") is True:
                    c.tax_basis = "Included"
                elif ps.get("valueAddedTaxIncluded") is False:
                    c.tax_basis = "Excluded"
                if ps.get("unitText"):
                    c.unit_text = str(ps["unitText"])
                out.append(c)
    # 2) microdata
    for m in pg.micro:
        if "name" in m and ("price" in m or "description" in m):
            out.append(RawCandidate(name=m.get("name"), sku=m.get("sku"), brand=m.get("brand"), specification=(m.get("description") or "")[:600] or None,
                                    price=_clean_price(m.get("price")), currency=_norm_currency(m.get("pricecurrency")), method="Microdata itemprop",
                                    price_valid_until=m.get("pricevaliduntil"), snippet=json.dumps(m, ensure_ascii=False)[:300]))
    # 3) OpenGraph product tags
    if "product:price:amount" in pg.meta and not out:
        out.append(RawCandidate(name=pg.meta.get("og:title") or pg.title, price=_clean_price(pg.meta.get("product:price:amount")),
                                currency=_norm_currency(pg.meta.get("product:price:currency")), specification=(pg.meta.get("og:description") or "")[:600] or None,
                                method="OpenGraph product tags", snippet=f"og:title={pg.meta.get('og:title')} amount={pg.meta.get('product:price:amount')}"))
    # 4) low-confidence text fallback: only when nothing structured exists
    if not out:
        found = list(PRICE_TEXT.finditer(text))
        for m in found[:5]:
            amt = _clean_price(m.group("a") or m.group("b"))
            if amt:
                ctx = text[max(0, m.start() - 80):m.end() + 80]
                out.append(RawCandidate(name=pg.meta.get("og:title") or pg.title or None, price=amt, currency=_norm_currency(m.group("cur") or m.group("cur2")),
                                        method="Text pattern (low confidence)", snippet=ctx, flags=["TEXT_PATTERN_ONLY"]))
        if not found:
            out.append(RawCandidate(name=pg.meta.get("og:title") or pg.title or None, specification=(pg.meta.get("og:description") or pg.meta.get("description") or "")[:600] or None,
                                    method="Page metadata (no price found)", snippet=(pg.title or "")[:200]))

    prices_by_key: dict[str, set[str]] = {}
    for c in out:
        if c.price:
            prices_by_key.setdefault((c.sku or c.name or "").lower(), set()).add(c.price)
    for c in out:
        _classify(c, text, host, retrieved_on, page_date, max_age_days, prices_by_key, pg.struck)
    return out


def _classify(c: RawCandidate, text: str, host: str, today: date, page_date: str | None, max_age_days: int,
              prices_by_key: dict[str, set[str]], struck: list[str]) -> None:
    ctx = (c.snippet + " " + text[:4000])
    # price kind
    if not c.price:
        c.price_kind = "Quote required" if QUOTE_PHRASES.search(text) else "Specification only"
        c.flags.append("NO_PRICE")
    elif struck and any(c.price.replace(".00", "") in re.sub(r"[^\d.]", "", s) or _clean_price(s) == c.price for s in struck):
        c.price_kind = "Promotional"
        c.flags.append("PROMOTIONAL")
    elif SALE.search(c.snippet):
        c.price_kind = "Promotional"
        c.flags.append("PROMOTIONAL")
    else:
        c.price_kind = "List price"
    # geography / currency
    cur = c.currency
    saudi_ev = []
    if cur == "SAR":
        saudi_ev.append("price in SAR")
    if host.endswith(".sa"):
        saudi_ev.append(f"domain {host}")
    m = SAUDI.search(text)
    if m:
        saudi_ev.append(f"page mentions '{m.group(0)}'")
    c.geography = ("Saudi Arabia (" + "; ".join(saudi_ev) + ")") if saudi_ev else "Unknown"
    if not saudi_ev:
        c.flags.append("GEOGRAPHY_UNKNOWN")
    if c.price and not cur:
        c.flags.append("CURRENCY_UNKNOWN")
    elif cur and cur != "SAR":
        c.flags.append("FOREIGN_CURRENCY")
    # tax / delivery / installation (page-level statements; explicit only)
    if c.tax_basis == "Unknown":
        i, e = bool(VAT_INC.search(ctx)), bool(VAT_EXC.search(ctx))
        c.tax_basis = "Included" if i and not e else "Excluded" if e and not i else "Unknown"
        if i and e:
            c.flags.append("VAT_STATEMENT_CONFLICT")
    if c.tax_basis == "Unknown" and c.price:
        c.flags.append("VAT_UNKNOWN")
    if DELIVERY_EXCLUDED.search(ctx):
        c.delivery_basis = "Supply only (excl. delivery)"
    elif DELIVERED.search(ctx):
        c.delivery_basis = "Delivered"
    if c.delivery_basis == "Unknown" and c.price:
        c.flags.append("DELIVERY_UNKNOWN")
    if INSTALL_INC.search(ctx):
        c.installation_included = "Yes"
    # unit
    if not c.unit_text:
        m = UNIT_TEXT.search(ctx)
        c.unit_text = m.group(1) if m else None
    if c.price and not c.unit_text:
        c.flags.append("UNIT_UNKNOWN")
    # freshness
    if c.price_valid_until:
        try:
            if date.fromisoformat(str(c.price_valid_until)[:10]) < today:
                c.flags.append("STALE_EXPIRED")
        except ValueError:
            c.flags.append("VALIDITY_DATE_UNPARSEABLE")
    if page_date:
        try:
            pd_ = date.fromisoformat(page_date[:10])
            c.page_date = pd_.isoformat()
            c.effective_date = pd_.isoformat()
            if (today - pd_).days > max_age_days:
                c.flags.append("STALE")
        except ValueError:
            pass
    if not c.effective_date:
        c.effective_date = today.isoformat()
        c.flags.append("NO_PAGE_DATE")             # effective date defaulted to the retrieval date
    if c.price and len(prices_by_key.get((c.sku or c.name or "").lower(), set())) > 1:
        c.flags.append("CONTRADICTORY")
    if "TEXT_PATTERN_ONLY" in c.flags:
        c.flags.append("LOW_CONFIDENCE_EXTRACTION")
