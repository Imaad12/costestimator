# Standards and evidence register

Generated from `data/standards/standards_register.json` by `scripts/gen_docs.py` (loaded into the table `standards_register`; CLI `python -m app.cli standards list|acquire|import`).
It records **where a rule or a basis comes from and what was actually read** - concise references and paraphrases only. It never reproduces copyrighted standards, never stores a price or a productivity value,
and **no row is a statement that a project complies** with anything. Every row needs human review before a governed parameter cites it. 'Verified' means the page text was read in that session; it does not mean the clause is current law or applicable to a project.

Source of these rows: web research performed in a Claude Code session on 2026-10-14 (not a human review). Access date 2026-10-14.

| ID | Topic | Title | Publisher | Edition / date | Clause / page | Status | Link or file |
|---|---|---|---|---|---|---|---|
| STD-001 | AACE cost estimate classification (generic 17R-97 and process industries 18R-97) | Professional Guidance Document No. 01 - Guide to Cost Estimate Classification Systems (Rev. August 29, 2022); it indexes RP 17R-97 and RP 18R-97 (Cost Estimate  | AACE International | PGD 01 Rev. August 29, 2022 (the RP texts 17R-97 / 18R-97 themselves were NOT opened; member download / paid) | PGD 01 sections: Introduction; Classification Concepts and Principles; Guide entries 17R-97 and 18R-97 | **Partially verified - secondary source** | https://library.aacei.org/pgd01/pgd01.shtml |
| STD-002 | AACE cost estimate classification - building and general construction (56R-08) | 56R-08: Cost Estimate Classification System - As Applied in Engineering, Procurement, and Construction for the Building and General Construction Industries | AACE International | RP number suffix -08 as listed; current revision date of the RP not seen (RP text not opened) | PGD 01 'Guide to Industry Specific Estimate Classification RPs' entry for 56R-08 | **Partially verified - secondary source** | https://library.aacei.org/pgd01/pgd01.shtml |
| STD-003 | Saudi Labor Law - normal hours, Ramadan hours, overtime premium, weekly rest | Actually working hours (HRSD Knowledge Centre, Labor Education); Overtime Hours (HRSD Knowledge Centre) | Ministry of Human Resources and Social Development (HRSD / MHRSD) | Authored 15 November 2019 (18 Rabi' Al-Awwal 1441); page cached 2026-10-12. Overtime page: https://www.hrsd.gov.sa/en/kn | Articles 98, 99, 100, 107 of the Labor Law as quoted on the page; overtime page cites Article 22 of the Executive Regula | **Partially verified - secondary source** | https://www.hrsd.gov.sa/en/knowledge-centre/articles/312 |
| STD-004 | Saudi Building Code (SBC) - authority and code families | Saudi Building Code (official site, English home and Building Code 2024 pages) - search-result excerpts only | Saudi Building Code National Committee / Saudi Building Code Center (sbc.gov.sa) | 2024 edition referenced in an official news item (edition detail not read) | Not read directly. Official-domain search excerpts for https://www.sbc.gov.sa/En/Pages/default.aspx and https://www.sbc. | **Not verified - requires human acquisition** | - |
| STD-005 | Saudi VAT - standard rate | Value Added Tax (ZATCA Rules and Regulations page) and Guideline for Amendments to the Implementing Regulation of Value Added Tax | Zakat, Tax and Customs Authority (ZATCA) | Guideline issued under ZATCA Board Resolution No. (01-06-24) dated November 19, 2024; VAT overview page https://zatca.go | Guideline section 1.3 'What is Value-Added Tax (VAT)?'; overview page table 'Goods and services subject to VAT' | **Verified - primary source read** | https://zatca.gov.sa/en/HelpCenter/guidelines/Documents/Amendments-to-the-Implementing-Regulation-of-%28VAT%29.PDF |
| STD-006 | Saudi official public holidays (Eid al-Fitr, Eid al-Adha, National Day, Founding | HOLIDAYS AND LEAVES (HRSD Knowledge Centre) | Ministry of Human Resources and Social Development (HRSD / MHRSD) | Authored 15 November 2019 (18 Rabi' Al-Awwal 1441) | Page body (no article numbers shown) | **Partially verified - secondary source** | https://www.hrsd.gov.sa/en/knowledge-centre/articles/322 |
| STD-007 | Government Tenders and Procurement Law and Implementing Regulations (reference f | Government Tenders and Procurement Law (MoF English PDF); Executive/Implementing Regulations; Etimad platform page; news item 'Saudi Minister of Finance Thanks  | Ministry of Finance (MoF), Saudi Arabia | Law PDF stamp seen 22/04/1442 H in search excerpt; Executive Regulations amended by Ministerial Resolution No. 3479 date | Search excerpts only: Law Articles 1, 2, 98 (supersedes earlier law M/58, 1427H); Executive Regulations Articles 8, 34,  | **Not verified - requires human acquisition** | https://www.mof.gov.sa/en/Documents/Government_Tenders_and_Procurement_Law.pdf |
| STD-008 | Saudi midday outdoor work ban in summer | Implementation of the Midday Work Ban Decision Begins on 15 June | Ministry of Human Resources and Social Development (HRSD / MHRSD) with the Natio | Authored 23 June 2026 (08 Muharram 1448); covers 2026 period | News item body | **Verified - primary source read** | https://www.hrsd.gov.sa/en/media-center/news/%D8%AA%D8%B7%D8%A8%D9%8A%D9%82-%D9%82%D8%B1%D8%A7%D8%B1-%D8%AD%D8%B8%D8%B1- |
| STD-009 | Productivity references - RSMeans / Gordian | RSMeans construction cost data publication family | Gordian (RSMeans) | - | - | **Not verified - requires human acquisition** | - |
| STD-010 | Productivity references - Spon's price books | Spon's price book family (e.g. Spon's Architects' and Builders' Price Book; Civil Engineering and Highway Works; Mechanical and Electrical Services) | Taylor & Francis / Routledge (publisher not verified here) | - | - | **Not verified - requires human acquisition** | - |
| STD-011 | Productivity references - CIOB guidance | CIOB publications on estimating and productivity (e.g. Code of Estimating Practice) | Chartered Institute of Building (CIOB) | - | - | **Not verified - requires human acquisition** | - |
| STD-012 | Productivity references - manufacturer installation instructions and company his | Manufacturer / supplier installation instructions and the company's own historical records | Individual manufacturers; the contractor itself | - | - | **Not verified - requires human acquisition** | - |

## What each row says and where it stops

### STD-001 - Professional Guidance Document No. 01 - Guide to Cost Estimate Classification Systems (Rev. August 29, 2022); it indexes

* **Scope:** Guide to AACE's estimate-classification recommended practices: five classes, Class 5 (least defined) to Class 1 (most defined); 17R-97 is the generic principles RP; 18R-97 is the process-industries application.
* **Paraphrase (not a quotation):** AACE describes five estimate classes (5 to 1, least to most defined). Per PGD 01, the maturity of scope definition is the primary determinant of class; end use, method, effort and accuracy are secondary. Accuracy ranges are indicative and not targets.
* **Limitations:** Verified from AACE's own guidance document about the RPs, not from the text of 17R-97 or 18R-97. Copyrighted; RP text is member/paid. Class definitions, maturity percentages and accuracy ranges in the RPs were not read and must not be copied from memory.
* **Notes:** PGD 01 is a primary AACE publication but only a pointer to the RPs, hence 'Partially verified'. Class purposes (e.g. Class 5 concept screening ... Class 1 check estimate) were NOT read on the AACE page and are not recorded; a person must acquire 17R-97/18R-97 to record them. The PGD notes class is not a contract specification for estimate quality. Never present accuracy percentages from memory.

### STD-002 - 56R-08: Cost Estimate Classification System - As Applied in Engineering, Procurement, and Construction for the Building 

* **Scope:** As listed by AACE: new or renovated buildings plus repetitive site/civil projects (e.g. site development, utilities, water and sewer pipelines); excludes process industries, road/rail, hydropower, tunnels, and one-of-a-kind special facilities.
* **Paraphrase (not a quotation):** AACE's guide lists 56R-08 as the building and general construction application of its five-class estimate classification, covering buildings and repeatable site/civil work, with listed exclusions for process, transport, hydropower and unique special-purpose facilities.
* **Limitations:** RP text not read (member download / non-member purchase). Only AACE's scope summary seen. Copyrighted.
* **Notes:** Most relevant AACE RP for a building-led KSA contractor; for oil and gas/process packages 18R-97 applies, and PGD 01 says mixed-scope projects should rate each WBS element with the most suitable RP. Human must buy/obtain RP text before the tool states class criteria.

### STD-003 - Actually working hours (HRSD Knowledge Centre, Labor Education); Overtime Hours (HRSD Knowledge Centre)

* **Scope:** Max actual working hours per day/week, reduced Ramadan hours for Muslims, overtime pay, overtime on public holidays.
* **Paraphrase (not a quotation):** HRSD's page states actual work may not exceed 8 hours a day or 48 a week, with Ramadan hours for Muslims reduced to no more than 6 a day or 36 a week. Overtime pays the hourly wage plus 50% of basic wage, hours on public holidays count as overtime, and the overtime page cites 720 additional hours per year (Executive Regulations Art. 22) unless the worker consents to more.
* **Limitations:** HRSD educational summary of the Law, not the gazetted text. Weekly rest day provision was NOT on the pages read (not recorded). A separate HRSD-hosted Labor Law PDF (2023-02/Labor.pdf) surfaced in search with different numbers (ten hours / forty-five hours in Art. 99) - appears to be an older or different text; versions conflict and were not reconciled. Applicability to non-Muslims, to specific industries and to site-specific rules (e.g. Minister decisions under Art. 99) must be checked by a person.
* **Notes:** Article numbers recorded are those printed on the HRSD page. Treat as official ministry summary; a human should confirm against the current Labor Law and Executive Regulations text (Bureau of Experts laws.boe.gov.sa was unreachable - DNS failure from this environment). Weekly rest: null here - not seen. Use only as sources for governed parameters, never as hard-coded defaults.

### STD-004 - Saudi Building Code (official site, English home and Building Code 2024 pages) - search-result excerpts only

* **Scope:** National building code system. Excerpts show code groups such as SBC 301-306 structural family, SBC 901 existing buildings, SBC 701-702 sanitary/health, SBC 601 energy conservation, and 'SBC 301 Saudi Code for Structural Design Loads, Seismic, and Wind', 'SBC 302 Saudi Code for Construction', 'SBC 303 Soils and Foundations'.
* **Paraphrase (not a quotation):** Search excerpts from the official SBC site name the structural codes SBC 301-306 and individual titles for 301, 302 and 303, plus health, energy and existing-building codes. A news excerpt says the 2024 edition added three new structural codes.
* **Limitations:** Direct page fetches of sbc.gov.sa failed (tunnel/proxy error), so the code list was not read in full. Full code texts are not recorded. Edition in force and any new 2024 codes must be confirmed.
* **Notes:** A person should open sbc.gov.sa, record the exact code list and edition. SBC is a reference for design requirements, not a source of estimating rates. Do not state SBC compliance of any project from this tool.

### STD-005 - Value Added Tax (ZATCA Rules and Regulations page) and Guideline for Amendments to the Implementing Regulation of Value 

* **Scope:** Standard VAT rate charged by VAT-registered persons in KSA.
* **Paraphrase (not a quotation):** ZATCA's guideline states VAT-registered persons must charge VAT at a standard rate of 15% where applicable, added to the final sale price. The ZATCA VAT overview page also shows 15% in its rate table.
* **Limitations:** Guideline English text is guidance only; Arabic prevails. Zero-rated/exempt supplies, construction-specific treatment (e.g. residential, exports, real estate) and any change after the document date were not assessed. The overview page's rate table rendered only a 'Food & Beverages 15%' row.
* **Notes:** Rate should still be entered as a governed tax parameter with this source and an effective date, approved by the Commercial Approver. Tax treatment per supply (zero-rated/exempt/reverse charge) needs a tax adviser. The first guessed URL (TaxesRegulations/Taxes/Pages/VAT.aspx) returned a ZATCA 'Not found page' and is not used.

### STD-006 - HOLIDAYS AND LEAVES (HRSD Knowledge Centre)

* **Scope:** Private-sector worker entitlement to Eid al-Fitr, Eid al-Adha and National Day holidays and how they interact with weekly rest and leave.
* **Paraphrase (not a quotation):** HRSD states workers are entitled to a 4-day Eid al-Fitr holiday starting the day after 29 Ramadan per the Umm Al-Qura calendar, a 4-day Eid al-Adha holiday starting from Arafat day, and the National Day on the first day of Libra, with compensation rules when holidays overlap rest days.
* **Limitations:** Page dates from 2019 and does not mention Founding Day, so Founding Day is NOT verified here. It states holiday starts by reference to the Umm Al-Qura calendar, so exact dates, any royal-order extensions and annual HRSD/Council of Ministers announcements must be checked each year. Public-sector leave regulation PDF surfaced in search but was not read.
* **Notes:** A project calendar MUST be confirmed each year by a human (moon sighting / annual decisions; Founding Day source still needed). Enter as governed calendar parameters, never as defaults.

### STD-007 - Government Tenders and Procurement Law (MoF English PDF); Executive/Implementing Regulations; Etimad platform page; news

* **Scope:** Rules governing government agency tenders, contracting and the Etimad e-portal; context for bid preparation by contractors.
* **Paraphrase (not a quotation):** MoF publishes an English Government Tenders and Procurement Law and Executive Regulations, and a 05/08/2026 MoF news headline says Cabinet approved a new Government Tenders and Procurement Law. Which text and regulations currently apply was not established.
* **Limitations:** Documents themselves were not opened (only search-result excerpts; a direct fetch of the MoF news page timed out). The August 2026 news headline indicates a new law has been approved, so the PDFs found may be superseded; implementing regulations for the new law were not seen. Not used for any cost value.
* **Notes:** A person must confirm the in-force law and regulations on mof.gov.sa and Etimad before relying on any rule (bid validity, guarantees, deadlines). Ministry of Municipal and Rural Affairs (Momrah) tender rules were not researched. Tool must not state procurement-law compliance.

### STD-008 - Implementation of the Midday Work Ban Decision Begins on 15 June

* **Scope:** Midday work ban for private-sector establishments for the 2026 season; violations reported via 19911.
* **Paraphrase (not a quotation):** HRSD announced the Midday Work Ban for all private-sector establishments from Monday 15 June 2026 until Tuesday 15 September 2026, between 12:00 p.m. and 3:00 p.m. It reports 94% compliance in 2025 and urges drinking water, shade, rest areas and protective equipment.
* **Limitations:** This is the 2026 announcement; dates are annual decisions, so a future year must be re-confirmed. Whether the ban applies by region or work type (exemptions) was not stated in the page read. The full text of the underlying decision was not read.
* **Notes:** Corroborated by an HRSD search excerpt of the my.gov.sa Labor page ('12:00 p.m. to 3:00 p.m., June 15 to September 15 of each year', page not opened in full). Enter as a governed calendar/productivity-window parameter per project year with this source; confirm annually and for the project region.

### STD-009 - RSMeans construction cost data publication family

* **Scope:** Commercial unit-cost and labour-hour reference publications (US-based).
* **Paraphrase (not a quotation):** Name only: recognised publication family; requires human acquisition - not verified.
* **Limitations:** Not accessed. Proprietary, licensed, US-centred; not KSA data. No numbers recorded.
* **Notes:** If licensed by the company, any productivity value must enter via a governed parameter with edition and page, human-approved, and be adjusted for KSA conditions by a person.

### STD-010 - Spon's price book family (e.g. Spon's Architects' and Builders' Price Book; Civil Engineering and Highway Works; Mechani

* **Scope:** UK-based price books containing labour constants and unit rates.
* **Paraphrase (not a quotation):** Name only: recognised publication family; requires human acquisition - not verified.
* **Limitations:** Not accessed. Proprietary, UK-centred. No numbers recorded.
* **Notes:** Edition titles and publisher listed from general knowledge only, not checked.

### STD-011 - CIOB publications on estimating and productivity (e.g. Code of Estimating Practice)

* **Scope:** Professional guidance on estimating practice.
* **Paraphrase (not a quotation):** Name only: recognised publication family; requires human acquisition - not verified.
* **Limitations:** Not accessed; exact titles and editions not checked. No numbers recorded.
* **Notes:** Methodology guidance rather than a KSA productivity dataset.

### STD-012 - Manufacturer / supplier installation instructions and the company's own historical records

* **Scope:** Product-specific installation methods; company actuals.
* **Paraphrase (not a quotation):** Name only: recognised source type; requires human acquisition - not verified.
* **Limitations:** Not accessed. Specific to each product/company. No numbers recorded.
* **Notes:** Company historical actuals are the usual basis for governed productivity parameters; each value needs a human-approved source row.

## Sources a person must still acquire

Every row whose status is not *Verified - primary source read* needs a person to obtain the document, record the edition and clause, and re-import the row. Until then the product treats it as **unverified** and states so in every document that cites it. Productivity references (RSMeans, Spon's, CIOB publications, manufacturer instructions, company actuals) are listed by **name only**; no number from them is stored anywhere in the product.

