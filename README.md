# SHM-AI Platform

**AI-Directed Predictive Maintenance & Structural Health Monitoring**

A modern, production-grade platform for detecting, measuring, and predicting structural defects in civil infrastructure using computer vision and engineering intelligence.

---

## Architecture

```
SHM-AI/
├── backend/          ← FastAPI REST API (Python 3.11)
├── vision/           ← Computer Vision Engine [Phase 2]
├── intelligence/     ← Structural Health Intelligence [Phase 3]
├── degradation/      ← Material Degradation Models [Phase 4]
├── recommendation/   ← AI Recommendation Engine [Phase 5]
├── frontend/         ← Streamlit Dashboard → React [Phase 6]
├── datasets/         ← Training data management
├── weights/          ← YOLO model weights (.pt files)
├── reports/          ← Generated inspection reports
├── tests/            ← Pytest test suite
├── scripts/          ← CLI utilities
└── deployment/       ← Docker + cloud deployment [Phase 7]
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | SQLAlchemy (async) + SQLite → PostgreSQL |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Vision | Ultralytics YOLO11 + PyTorch |
| Dashboard | Streamlit (Phase 6) → React |
| Testing | Pytest + pytest-asyncio |

## Quick Start (Phase 1)

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux

# Install core dependencies
pip install -e ".[dev]"

# Copy environment file
copy .env.example .env
```

### Run the API server

```bash
python scripts/run_dev.py
```

Or directly:
```bash
uvicorn backend.app.main:app --reload --port 8000
```

### API Documentation
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- Health check: http://localhost:8000/api/v1/system/health

### Run tests

```bash
pytest tests/ -v
```

---

## Build Phases

| Phase | Status | Description |
|---|---|---|
| 1 — Foundation | ✅ **Complete** | FastAPI, SQLAlchemy, DI, CRUD API |
| 2 — Vision Engine | ✅ **Complete** | YOLO11 detection, segmentation, measurements |
| 3 — Health Intelligence | ✅ **Complete** |Health scoring, severity classification, engineering rules, risk assessment |
| 4 — Degradation | 🔜 Pending | Carbonation, corrosion, service life |
| 5 — Recommendations | 🔜 Pending | Repair actions, PDF reports |
| 6 — Dashboard | 🔜 Pending | Streamlit monitoring UI |
| 7 — Deployment | 🔜 Pending | Docker, GPU, auth, benchmarks |

---

## Reference
This platform supersedes the legacy *WhatTheCrack* (YOLOv8/PySide6) desktop application.
Selected algorithms (skeletonization, crack graph topology, sliced inference) have been
extracted and rewritten using modern best practices.
