# Standard assembly structures

`standard_assemblies.csv` lists **structure only**: which resource categories typically make up a unit of completed work.
Every consumption factor, waste factor, productivity and crew value is deliberately **blank** - they are not verified Saudi
benchmarks and must be supplied by the estimator from the company's own data, then reviewed and approved in the application.

* Loaded as **Draft** assemblies (`STD-*`). A Draft assembly cannot be mapped to a BOQ item and cannot be approved until every
  factor is filled (`assemblies.validate` reports "consumption factor is missing").
* Clone one into your project or company library with *Assemblies -> Clone*, fill the factors, submit and approve.
* The synthetic `DEMO-A-*` assemblies (loaded by `python -m app.cli demo`) carry invented factors and are clearly labelled.
