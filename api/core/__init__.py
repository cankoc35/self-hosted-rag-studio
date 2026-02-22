"""
Shared, cross-cutting code for the API.

`core/` should contain small building blocks that multiple features use
(DB wiring, settings, logging). Keep feature-specific SQL and business logic
in the corresponding feature package (e.g. `ingestion/`).
"""

