# Structural Health Intelligence — Phase 3

**Status**: 🔜 Not yet implemented. Awaiting Phase 2 approval.

## Planned Modules

```
intelligence/
├── scoring/
│   ├── health_scorer.py         ← 0–100 health score calculator
│   └── severity_classifier.py  ← Low / Medium / High / Critical classification
├── rules/
│   ├── engineering_rules.py     ← Crack location → failure mode mapping
│   └── risk_engine.py           ← Risk aggregation from multiple defects
└── schemas.py                   ← Shared intelligence schemas
```

## Engineering Rules Engine

| Crack Location | Failure Mode |
|---|---|
| Beam (bottom) | Flexural tension failure |
| Column (vertical) | Compression / buckling |
| Diagonal (45°) | Shear failure |
| Slab (grid pattern) | Two-way bending / punching shear |

## Health Score Formula (0–100)
- 100 = Pristine / No damage
- 75–99 = Minor defects
- 50–74 = Moderate — schedule inspection
- 25–49 = Severe — urgent repair
- 0–24 = Critical — immediate action required
