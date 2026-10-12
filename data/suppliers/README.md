# Suppliers

No real supplier is shipped. `supplier_schema.csv` is the import layout (header only). Rules:
* Contact details may be entered **only with a traceable `contact_source`** and a stated permitted use.
* The application never sends email and never infers contact details.
* Synthetic demo suppliers (`DEMO Supplier A/B/C [SYNTHETIC]`) are created by `python -m app.cli demo` and carry no contact data.
