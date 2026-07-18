# Material Degradation Engine — Phase 4

**Status**: ✅ Implemented (Phase 4 Foundation & Service Life Orchestration).

Deterministic, physics-based material degradation models for reinforced concrete structures. Fully decoupled from the backend ORM layer and downstream API routes.

## Module Architecture

```
degradation/
├── __init__.py           ← Package surface & public exports
├── models.py             ← Pure domain vocabulary (ExposureClass EN 206 XC1–XC4, MaterialProperties)
├── config.py             ← Tunable coefficient tables (CarbonationCoefficient, CorrosionRateEntry, MaintenanceThreshold)
├── schemas.py            ← Pydantic I/O contracts (DegradationAssessmentInput, Projections, MaintenanceDecision)
├── carbonation.py        ← CarbonationModel: carbonation depth front & depassivation time
├── corrosion.py          ← CorrosionModel: initiation logic & exponential saturating corrosion index
└── service_life.py       ← ServiceLifeEstimator: orchestrator & MaintenanceDecision evaluator
```

## Core Physics & Logic

### 1. Carbonation Model (`CarbonationModel`)
Predicts carbonation front depth using a square-root-of-time diffusion model:
$$d_c(t) = k_c \cdot \sqrt{t}$$
where $k_c$ is adjusted for concrete water/cement ratio deviation from reference values:
$$k_c = k_{c,\text{base}} + \text{slope} \cdot (w/c - w/c_{\text{ref}})$$
Time to depassivation occurs when carbonation depth equals concrete cover:
$$t_{\text{dep}} = \left(\frac{\text{cover}}{k_c}\right)^2$$

### 2. Corrosion Model (`CorrosionModel`)
Evaluates corrosion initiation and propagation:
- **Initiation Signals**:
  - *Primary*: Carbonation depth front reaches/passes concrete cover ($t \ge t_{\text{dep}}$).
  - *Secondary (Fallback)*: Observed `SEVERE` or `CRITICAL` corrosion defects from inspection, conservatively triggering initiation even if carbonation depth has not yet reached cover.
- **Propagation Index**:
  Deterministic saturating index in $[0, 1]$ computed from elapsed years since initiation $\tau$:
  $$\text{Corrosion Index} = 1 - e^{-\tau / \tau_{\text{sat}}}$$

### 3. Service Life Estimator & Maintenance Decision (`ServiceLifeEstimator`)
Orchestrates single-pass execution of `CarbonationModel` followed by `CorrosionModel`. Evaluates projections against `MaintenanceThreshold` to produce a typed `MaintenanceDecision`:
- `corrosion_index_exceeds_ceiling`: True if corrosion index $\ge$ ceiling.
- `carbonation_exceeds_cover_fraction`: True if carbonation depth $\ge$ cover fraction limit.
- `secondary_initiation_triggered`: True if initiation was triggered by observed severe/critical defects.
- `maintenance_required`: True if any of the above conditions hold. Resolves the contradiction where observed physical corrosion damage would otherwise be missed by raw probability thresholds.

## Design & Decoupling Constraints
- **Zero ORM Coupling**: No imports from `backend.app.models`.
- **Typed I/O Schemas**: Domain Pydantic models define all contracts in `degradation/schemas.py`.
- **Config-Driven Physics**: Config tables in `degradation/config.py` are frozen dataclasses overridable at runtime per engine instance.
- **Deterministic**: No ML, learned parameters, or probabilistic randomness.
