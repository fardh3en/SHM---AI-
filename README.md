# SHM-AI Platform

> **AI-Directed Predictive Maintenance & Structural Health Monitoring**

SHM-AI is a modular, production-oriented platform that combines **computer vision**, **structural engineering intelligence**, and **deterministic material degradation modelling** to automate the inspection, assessment, and maintenance planning of civil infrastructure.

The platform is designed to evolve from crack detection into a complete engineering decision-support system capable of assisting inspectors, engineers, and infrastructure managers.

---

# Features

## ✅ Phase 1 — Backend Foundation
- FastAPI REST API
- Async SQLAlchemy ORM
- SQLite (PostgreSQL-ready)
- Alembic database migrations
- Dependency Injection architecture
- Pydantic v2 validation
- CRUD endpoints
- Modular project structure

---

## ✅ Phase 2 — Vision Engine
- YOLO11 crack detection
- Crack segmentation
- Measurement pipeline
- Detection persistence
- Vision orchestration service
- Quality improvements
- Extensible detector interface

---

## ✅ Phase 3 — Structural Health Intelligence
- Structural Health Score
- Severity Classification
- Engineering Rules Engine
- Risk Assessment Engine
- Assessment Service orchestration
- Deterministic engineering logic
- Strongly typed assessment schemas

---

## ✅ Phase 4 — Material Degradation
- Carbonation modelling
- Corrosion initiation modelling
- Service-life estimation
- Maintenance decision engine
- Deterministic engineering models
- Configurable engineering parameters
- Typed degradation schemas
- Comprehensive unit tests

---

# Architecture

```
SHM-AI/
│
├── backend/               # FastAPI REST API
│
├── vision/                # AI crack detection & measurement
│
├── intelligence/          # Structural health assessment
│
├── degradation/           # Material deterioration modelling
│
├── recommendation/        # Maintenance recommendation engine (Phase 5)
│
├── frontend/              # Dashboard (Phase 6)
│
├── datasets/              # Training datasets
│
├── weights/               # YOLO model weights
│
├── reports/               # Generated inspection reports
│
├── tests/                 # Unit & integration tests
│
├── scripts/               # Development utilities
│
└── deployment/            # Docker & cloud deployment (Phase 7)
```

---

# Technology Stack

| Layer | Technology |
|--------|------------|
| API | FastAPI + Uvicorn |
| Database | SQLAlchemy (Async) |
| Database Engine | SQLite → PostgreSQL |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Computer Vision | Ultralytics YOLO11 |
| Deep Learning | PyTorch |
| Testing | Pytest + pytest-asyncio |
| Dashboard | Streamlit → React |
| Language | Python 3.11+ |

---

# Quick Start

## Prerequisites

- Python 3.11+
- Git

---

## Installation

```bash
git clone https://github.com/fardh3en/SHM---AI-.git

cd SHM---AI-

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

pip install -e ".[dev]"

copy .env.example .env
```

---

## Run Development Server

```bash
python scripts/run_dev.py
```

or

```bash
uvicorn backend.app.main:app --reload --port 8000
```

---

## API Documentation

Swagger

```
http://localhost:8000/api/v1/docs
```

ReDoc

```
http://localhost:8000/api/v1/redoc
```

Health Check

```
http://localhost:8000/api/v1/system/health
```

---

## Run Tests

```bash
pytest tests/ -v
```

---

# Development Roadmap

| Phase | Status | Description |
|--------|--------|-------------|
| Phase 1 | ✅ Complete | Backend Foundation |
| Phase 2 | ✅ Complete | Vision Engine |
| Phase 3 | ✅ Complete | Structural Health Intelligence |
| Phase 4 | ✅ Complete | Material Degradation |
| Phase 5 | 🔜 Planned | Recommendation Engine |
| Phase 6 | 🔜 Planned | Monitoring Dashboard |
| Phase 7 | 🔜 Planned | Production Deployment |

---

# Project Milestones

| Version | Milestone |
|----------|-----------|
| **v0.1.0** | Backend Foundation |
| **v0.2.0** | Vision Engine |
| **v0.3.0** | Structural Health Intelligence |
| **v0.4.0** | Material Degradation |

---

# Roadmap Checklist

- [x] Backend Foundation
- [x] Vision Engine
- [x] Structural Health Intelligence
- [x] Material Degradation
- [ ] Recommendation Engine
- [ ] Dashboard
- [ ] Production Deployment

---

# Design Principles

The project follows several core engineering principles:

- Modular architecture
- Deterministic engineering models
- Strong type safety
- High testability
- Separation of concerns
- Extensible AI pipeline
- Production-oriented codebase
- Domain-driven package organization

---

# Project Vision

The long-term objective of SHM-AI is to provide an end-to-end intelligent infrastructure inspection platform capable of:

- Detecting structural defects
- Measuring crack characteristics
- Assessing structural health
- Predicting material deterioration
- Estimating remaining service life
- Generating maintenance recommendations
- Producing engineering reports
- Supporting large-scale infrastructure asset management

---

# Legacy Reference

SHM-AI supersedes the legacy **WhatTheCrack** desktop application.

Several concepts—including crack topology, skeletonization, and measurement workflows—have been redesigned and reimplemented using a modern, modular architecture suitable for production deployment.

---

## Author

**Fardheen Ahammed**

B.Tech Computer Science & Engineering

Building AI-driven solutions for structural health monitoring and predictive maintenance.

---