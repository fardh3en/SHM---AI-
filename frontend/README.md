# Dashboard — Phase 6

**Status**: 🔜 Not yet implemented. Awaiting Phase 5 approval.

## Planned Modules

```
frontend/
└── dashboard/
    ├── app.py              ← Streamlit app entry point
    ├── pages/
    │   ├── 01_assets.py    ← Asset registry + health overview
    │   ├── 02_inspect.py   ← Run inspection, upload image/video
    │   ├── 03_gallery.py   ← Defect image gallery with filters
    │   ├── 04_trends.py    ← Health score trend analysis
    │   ├── 05_degradation.py ← Degradation forecast charts
    │   └── 06_reports.py   ← Generate & export PDF reports
    └── components/
        ├── health_gauge.py     ← Health score gauge widget
        ├── defect_map.py       ← Spatial defect heatmap
        └── timeline.py         ← Inspection timeline chart
```

## Future
Phase 6 implements Streamlit as a temporary dashboard.
A React + TypeScript frontend will replace it in a future phase.
