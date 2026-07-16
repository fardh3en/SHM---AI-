# Material Degradation Engine — Phase 4

**Status**: 🔜 Not yet implemented. Awaiting Phase 3 approval.

## Planned Modules

```
degradation/
├── models/
│   ├── carbonation.py           ← Carbonation depth model (Papadakis equation)
│   ├── corrosion.py             ← Corrosion probability model
│   ├── chloride.py              ← Fick's second law chloride diffusion
│   └── freeze_thaw.py           ← Freeze-thaw cycle degradation
└── service.py                   ← Remaining Service Life (RSL) aggregator
```

## Physics Models

### Carbonation Depth (Papadakis)
`d_c = k_c * sqrt(t)` where k_c is environment-dependent carbonation coefficient.

### Chloride Diffusion (Fick's 2nd Law)
`C(x,t) = C_s * [1 - erf(x / (2 * sqrt(D_c * t)))]`

### Remaining Service Life
Integrates all degradation models → outputs years to critical threshold.
