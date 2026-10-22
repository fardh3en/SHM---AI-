# AI Recommendation Engine & Reporting — Phase 5

**Status**: ✅ Implemented & Tested

The **Recommendation Engine** transforms structural health intelligence and material degradation projections into actionable civil maintenance interventions, cost projections, and formal engineering report dossiers.

---

## Architecture & Modules

```
recommendation/
├── templates/
│   └── report.html.j2           ← Jinja2 structural engineering dossier template
├── config.py                    ← Cost tables, maintenance urgency matrix & thresholds
├── cost_estimator.py            ← Parametric maintenance and repair cost calculator
├── engine.py                    ← Decision engine (Monitor / Inspect / Repair / Replace)
├── recommendation_service.py    ← Service coordinating decision logic and cost estimates
├── report_generator.py          ← Jinja2 HTML and PDF engineering report generator
└── schemas.py                   ← Strongly-typed Pydantic recommendation schemas
```

---

## Decision Logic & Action Categories

The recommendation engine evaluates structural health scores, risk levels, and predicted service life:

| Health Score Range | Risk Classification | Primary Recommendation | Priority Level | Operational Action |
|:---:|:---:|:---:|:---:|:---|
| **75–100** | LOW | **MONITOR** | Routine | Schedule regular visual inspection in 24 months |
| **50–74** | MEDIUM | **INSPECT** | Medium | Conduct detailed non-destructive testing (NDT) within 6 months |
| **25–49** | HIGH | **REPAIR** | High | Structural crack injection, spall patch, and seal within 60 days |
| **0–24** | CRITICAL | **EMERGENCY / REPLACE** | Critical | Immediate load restriction, shoring, and component replacement |

---

## Parametric Cost Estimation (`cost_estimator.py`)

Calculates baseline budgetary estimates considering:
- Defect severity and spatial envelope (square footage / linear crack meters).
- Specialized equipment access factors (under-bridge platforms, scaffolding, aerial lifts).
- Structural materials (epoxy injection resins, rapid-setting polymer mortars, zinc galvanic anodes).

---

## Engineering Report Generation (`report_generator.py`)

Generates comprehensive civil engineering dossiers using Jinja2 templates (`report.html.j2`):
- **Executive Summary**: Asset details, assessment date, overall health index.
- **Defect Registry**: High-resolution imagery, localized defect bounding coordinates, and confidence levels.
- **Material Degradation Curves**: Carbonation progression and corrosion index projections.
- **Action Plan**: Prioritized interventions with estimated budgetary ranges and engineering sign-off fields.
- **Output Formats**: In-browser preview, stand-alone HTML, and printable PDF documents.
