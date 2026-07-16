# AI Recommendation Engine — Phase 5

**Status**: 🔜 Not yet implemented. Awaiting Phase 4 approval.

## Planned Modules

```
recommendation/
├── engine.py           ← Decision engine: Repair / Replace / Inspect / Monitor
├── cost_estimator.py   ← Estimated repair cost calculator
└── pdf_exporter.py     ← WeasyPrint PDF report generator
```

## Decision Logic

| Health Score | Risk Level | Recommended Action |
|---|---|---|
| 75–100 | Low | Monitor — next inspection in 2 years |
| 50–74 | Medium | Inspect — detailed visual + NDT |
| 25–49 | High | Repair — schedule within 6 months |
| 0–24 | Critical | Emergency — immediate structural intervention |

## PDF Report Contents
- Asset summary
- Inspection metadata
- Defect gallery (annotated images)
- Health score trend chart
- Degradation forecast curves
- Recommended actions + estimated costs
- Engineer sign-off section
