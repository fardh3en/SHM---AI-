# SHM-AI

<div align="center">

### AI-Directed Predictive Maintenance & Structural Health Monitoring

*A modular engineering platform that combines Computer Vision, Structural Engineering Intelligence, and Material Degradation Modelling for automated infrastructure inspection.*

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-YOLO11-orange.svg)
![Status](https://img.shields.io/badge/Status-Phase%204%20Complete-success.svg)
![Version](https://img.shields.io/badge/Version-v0.4.0-blue.svg)

</div>

---

# Overview

SHM-AI is a modular AI platform for structural inspection and predictive maintenance of civil infrastructure.

The project integrates:

- Computer Vision for crack detection and measurement
- Structural Health Intelligence for engineering assessment
- Material Degradation Models for deterioration prediction
- Future Recommendation Engine for maintenance planning

The architecture is intentionally modular so each engineering discipline remains independent, testable, and extensible.

---

# Current Progress

| Phase | Status |
|--------|--------|
| Backend Foundation | ✅ Complete |
| Vision Engine | ✅ Complete |
| Structural Health Intelligence | ✅ Complete |
| Material Degradation | ✅ Complete |
| Recommendation Engine | 🔜 Planned |
| Dashboard | 🔜 Planned |
| Deployment | 🔜 Planned |

---

# Architecture

```
                           SHM-AI

                 ┌────────────────────┐
                 │   Image Upload     │
                 └─────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Vision Engine       │
                │ YOLO11 Detection    │
                │ Measurements        │
                └─────────┬───────────┘
                          │
                          ▼
           ┌────────────────────────────┐
           │ Structural Intelligence    │
           │ • Health Score             │
           │ • Severity                 │
           │ • Engineering Rules        │
           │ • Risk Assessment          │
           └───────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ Material Degradation        │
          │ • Carbonation               │
          │ • Corrosion                 │
          │ • Service Life              │
          │ • Maintenance Decision      │
          └───────────┬─────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │ Recommendation Engine        │
        │ (Phase 5)                    │
        └───────────┬──────────────────┘
                    │
                    ▼
        ┌──────────────────────────────┐
        │ Dashboard & Reports          │
        └──────────────────────────────┘
```

---

# Project Structure

```
SHM-AI/

backend/            FastAPI backend
vision/             AI crack detection
intelligence/       Structural health assessment
degradation/        Material deterioration models
recommendation/     Maintenance planning
frontend/           Dashboard
tests/              Unit tests
deployment/         Production deployment
datasets/           Training data
weights/            YOLO weights
reports/            Generated reports
scripts/            Development utilities
```

---

# Technology Stack

| Category | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| API | FastAPI |
| ORM | SQLAlchemy Async |
| Validation | Pydantic v2 |
| Database | SQLite / PostgreSQL |
| Migrations | Alembic |
| AI | Ultralytics YOLO11 |
| Deep Learning | PyTorch |
| Testing | Pytest |

---

# Features

## Phase 1 — Backend Foundation

- FastAPI REST API
- Async SQLAlchemy
- Alembic migrations
- Dependency Injection
- CRUD APIs
- Modular architecture

---

## Phase 2 — Vision Engine

- YOLO11 crack detection
- Crack measurements
- Detection persistence
- Extensible detector pipeline
- Vision orchestration

---

## Phase 3 — Structural Health Intelligence

- Structural Health Score
- Severity Classification
- Engineering Rules Engine
- Risk Assessment
- Assessment orchestration

---

## Phase 4 — Material Degradation

- Carbonation modelling
- Corrosion initiation
- Service-life estimation
- Maintenance decision engine
- Deterministic engineering models
- Strongly typed schemas
- Unit tested implementation

---

# Quick Start

Clone the repository

```bash
git clone https://github.com/fardh3en/SHM---AI-.git
cd SHM---AI-
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate

Windows

```bash
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -e ".[dev]"
```

Run the API

```bash
python scripts/run_dev.py
```

or

```bash
uvicorn backend.app.main:app --reload
```

---

# API Documentation

Swagger

```
http://localhost:8000/api/v1/docs
```

ReDoc

```
http://localhost:8000/api/v1/redoc
```

---

# Testing

Run all tests

```bash
pytest tests/ -v
```

---

# Version History

| Version | Milestone |
|-----------|-----------|
| **v0.1.0** | Backend Foundation |
| **v0.2.0** | Vision Engine |
| **v0.3.0** | Structural Health Intelligence |
| **v0.4.0** | Material Degradation |

---

# Roadmap

- [x] Backend Foundation
- [x] Vision Engine
- [x] Structural Health Intelligence
- [x] Material Degradation
- [ ] Recommendation Engine
- [ ] Dashboard
- [ ] Deployment

---

# Engineering Principles

- Modular architecture
- Deterministic engineering models
- Type-safe implementation
- Test-driven development
- Separation of concerns
- Extensible AI pipeline
- Production-oriented codebase

---

# Future Vision

SHM-AI aims to become an end-to-end platform capable of:

- Detecting structural defects
- Measuring crack characteristics
- Assessing structural health
- Predicting material deterioration
- Estimating remaining service life
- Recommending maintenance actions
- Generating engineering reports
- Supporting infrastructure asset management

---

# Legacy

SHM-AI supersedes the earlier **WhatTheCrack** desktop application.

Core ideas such as crack topology and measurement workflows have been redesigned using a modular, production-ready architecture.

---

# Author

**Fardheen Ahammed**

B.Tech Computer Science & Engineering

*"Building AI-driven engineering systems for structural health monitoring."*

---

⭐ If you found this project interesting, consider starring the repository.