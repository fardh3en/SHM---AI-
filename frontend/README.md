# SHM-AI Frontend Workspace

<div align="center">

### Interactive Structural Health Monitoring Engineering Workspace

[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6.3-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0.1-646CFF.svg)](https://vitejs.dev/)
[![Three.js](https://img.shields.io/badge/Three.js-0.186.1-black.svg)](https://threejs.org/)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)

</div>

---

## Overview

The **SHM-AI Frontend** is a modern single-page application built for structural engineers and infrastructure inspection managers. Designed around high-precision workflows, it combines real-time computer vision review, interactive 3D digital twins, multi-step inspection recording, and automated engineering report generation.

---

## Key Features & Feature Modules

### 1. Interactive 3D Structural Health Digital Twin (`/structural-health`)
- **Location**: `src/features/visualization/`
- **Engine**: Three.js with custom OrbitControls and lighting setup.
- **Parametric Typologies**:
  - **Bridges**: Girder decks, structural piers, abutment footings, suspension cables.
  - **Roads / Flyovers**: Elevated multi-span highway decks, columns, barriers.
  - **Dams**: Curvature arch/gravity wall facades, crest parapets, spillways, intake conduits.
  - **Tunnels**: Vaulted concrete liners, tunnel portals, invert slabs.
  - **Buildings**: Multi-bay concrete columns, structural slabs, shear walls.
  - **Pipelines**: Cylindrical conduit sections, flanges, saddle supports.
- **Interactivity**: Element raycasting, component selection, defect heatmap projection, and evidence photo linkage.

### 2. Vision Analysis Studio (`/vision`)
- **Location**: `src/features/vision/`
- **Functionality**:
  - Split-screen comparison (original survey photography vs. YOLO26/YOLO11 defect localization canvas).
  - Prominent **Generate Engineering Report** button enabling 1-click dossier compilation for completed inspections with live preview redirection.
  - Ergonomic two-row toolbar layout separating inspection selectors from operational actions.
  - Interactive **Metric Scale Calibration Tool** (Ground Sampling Distance governance, mm/px unit toggles, and calibration badges).
  - Ad-hoc testing with **Analyze Another Image** direct upload and inspection creation.
  - Interactive SVG defect overlays with translucent polygon masks and hover telemetry cards.

### 3. Inspection Studio (`/inspections`)
- **Location**: `src/features/inspections/`
- **Workflow & Continuity**:
  - Deep linking and state continuity via `?inspectionId=...` and `?assetId=...` query parameters.
  - Automatic preloading of persisted evidence and inspection state, eliminating redundant image re-uploads.
  - Visual status banner: "Continuing Inspection <id>" with an explicit "Start New Inspection" action to reset state cleanly.
  - 4-Step guided inspection execution: Asset Selection → Evidence Attachment → Vision Pipeline Execution → Diagnostic Findings.
  - Findings Card featuring quick-action shortcuts to Vision Studio and instant Engineering Report compilation.

### 4. Engineering Reports (`/reports`)
- **Location**: `src/features/reports/`
- **Functionality**:
  - Compilation of official structural engineering dossiers rendered in the **Architectural Olive & Sand** design identity.
  - Real-time in-browser live iframe preview with deep linking support (`?reportFile=...`).
  - Report archive registry with per-row **Preview** switching to inspect historical dossiers instantly.
  - Standalone portability: Self-contained base64 Data URIs embedded directly into HTML documents for offline viewing without broken images.
  - One-click HTML dossier download and print-ready PDF export styling.

### 5. Asset Registry & Details (`/assets` & `/assets/:id`)
- **Location**: `src/features/assets/`
- **Functionality**:
  - Searchable, filterable structural asset inventory.
  - Detailed asset specifications, structural component breakdowns, and historical inspection timelines.

### 6. Executive Dashboard (`/dashboard`)
- **Location**: `src/features/dashboard/`
- **Functionality**:
  - High-level KPIs: Total assets, active inspections, critical defects, fleet health score.
  - Condition distribution charts and recent inspection activity streams.

---

## Directory Structure

```
frontend/
├── src/
│   ├── api/               # API clients (assets, inspections, vision, reports)
│   ├── components/        # Shared UI components
│   │   ├── layout/        # AppShell, Sidebar, Header, Breadcrumbs
│   │   └── ui/            # Buttons, Badges, Modals, Spinners, Tooltips
│   ├── features/          # Domain feature pages & logic
│   │   ├── assets/        # AssetListPage, AssetDetailPage, AssetModal
│   │   ├── dashboard/     # Dashboard metrics & condition charts
│   │   ├── home/          # Public landing / entry page
│   │   ├── inspections/   # InspectionStudioPage, InspectionFindingsCard
│   │   ├── reports/       # ReportsPage & DossierPreview
│   │   ├── vision/        # VisionAnalysisPage, DefectOverlayCanvas
│   │   └── visualization/ # StructuralHealthPage, Three.js 3D viewport & models
│   ├── hooks/             # Custom React hooks (useAsset, useInspection)
│   ├── tokens/            # Design tokens (colors, typography, spacing)
│   ├── App.tsx            # Main application router
│   ├── index.css          # Global CSS & Tailwind directives
│   └── main.tsx           # React bootstrap
├── package.json           # npm dependencies and scripts
├── tsconfig.json          # TypeScript compiler configuration
└── vite.config.ts         # Vite bundler configuration & backend API proxy
```

---

## Development Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
The frontend starts on [http://localhost:3000](http://localhost:3000) and automatically proxies `/api/v1` and `/uploads` requests to the FastAPI backend running on port 8000.

### 3. Verification Commands
```bash
# Type-check TypeScript codebase
npm run type-check

# Run ESLint
npm run lint

# Compile production bundle
npm run build
```
