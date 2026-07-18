"""
SHM-AI Structural Health Intelligence — Phase 3.

Domain layer responsible for turning raw defect observations (produced by
the Phase 2 Computer Vision Engine) into structural health assessments:
composite health scores, risk classification, severity breakdowns, and
identified failure modes.

This package is intentionally decoupled from persistence (backend.app.models)
and from the API layer. It defines pure domain schemas and abstract
interfaces only — concrete scoring/classification/rules logic is implemented
in later Phase 3 milestones, once this foundation is approved.
"""
