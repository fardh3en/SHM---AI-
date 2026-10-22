# Structural Health Intelligence — Phase 3

**Status**: ✅ Implemented & Tested

The **Structural Health Intelligence** package translates raw geometric and computer vision detections into civil structural engineering insights, failure mode predictions, and risk classifications.

---

## Architecture & Modules

```
intelligence/
├── scoring/
│   ├── health_scorer.py         ← Deterministic 0–100 Structural Health Score calculator
│   └── __init__.py
├── assessment_service.py        ← Orchestrator coordinating rules, scoring, and severity
├── engineering_rules.py         ← Location & morphology to structural failure mode mapping
├── interfaces.py                ← Abstract engine interfaces (IScorer, IClassifier, IRiskEngine)
├── risk_engine.py               ← Multi-defect aggregation & risk level escalation
├── schemas.py                   ← Strongly-typed Pydantic intelligence contracts
└── severity_classifier.py       ← ACI 224R / Eurocode 2 defect severity grading
```

---

## Core Engineering Intelligence

### 1. Structural Failure Mode Mapping (`engineering_rules.py`)
Codifies civil engineering principles mapping defect locations, orientations, and structural member types to fundamental structural mechanics:

| Structural Element | Crack Morphology | Inferred Failure Mode | Engineering Risk |
|---|---|---|---|
| **Beam / Girder** | Vertical at bottom (mid-span) | Flexural tension failure | Yielding of main tensile reinforcement |
| **Beam / Pier Cap** | Diagonal (~45°) near support | Shear failure | Diagonal tension / stirrup deficit |
| **Column / Pier** | Vertical parallel to axis | Compression / buckling | Core concrete crushing or hoop tie rupture |
| **Slab / Deck** | Radial / grid pattern | Two-way flexure / punching | Excessive deflections / punching shear |
| **Joint / Connection** | Diagonal / cruciform | Beam-column joint distress | Anchorage slip / shear distortion |

### 2. Defect Severity Classification (`severity_classifier.py`)
Classifies damage according to established concrete durability standards:
- **`CRITICAL`**: Active structural failure signs, wide cracks ($> 1.0\text{ mm}$), extensive delamination, or exposed buckled rebar.
- **`HIGH`**: Structural cracks ($0.4\text{ mm} - 1.0\text{ mm}$), moderate spalling, active water seepage with efflorescence.
- **`MEDIUM`**: Durability concerns ($0.2\text{ mm} - 0.4\text{ mm}$), minor spalls without rebar exposure.
- **`LOW`**: Superficial shrinkage or hairline cracks ($< 0.2\text{ mm}$).

### 3. Structural Health Score (0–100) (`health_scorer.py`)
Computes a repeatable, deterministic condition metric:
- **`100`**: Pristine / baseline condition (no damage detected).
- **`75–99`**: Minor non-structural defects (good condition).
- **`50–74`**: Moderate degradation (fair condition — routine maintenance required).
- **`25–49`**: Severe damage (poor condition — urgent repair required).
- **`0–24`**: Critical structural hazard (immediate intervention / load restriction).
