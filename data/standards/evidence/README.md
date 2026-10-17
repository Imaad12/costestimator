# Standards evidence (local copies)

PDFs of standards, laws and ministry pages that a person supplied as evidence for rows of the standards register live here **on your machine only** (they are copyrighted; `*.pdf` is git-ignored).
`evidence_manifest.json` lists each file with its SHA-256 and the register row it supports, so you can check you hold the same file. A register row cites its file in `notes` and, where there is no web link, in `url` as `file:data/standards/evidence/<name>`.
The application never reads these PDFs: a person (or an assistant session) reads the document and records the edition, clause/page and a short paraphrase in the register.
