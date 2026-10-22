/**
 * X-Ray Building Structural Data Models
 * Defines structural members, floor elevations, crack geometry, depth metrics,
 * reinforcement condition, and deterioration findings for full-scene X-Ray diagnostics.
 */

export type XRayViewingMode = 'exterior' | 'xray' | 'structure' | 'defects'

export type BuildingFloor = 'Roof' | 'F4' | 'F3' | 'F2' | 'F1' | 'GF'

export interface DefectDiagnosticTelemetry {
  crackId: string
  associatedAsset: string
  associatedInspection: string
  componentId: string
  componentName: string
  gridLocation: string
  floorLevel: string
  crackType: string
  lengthMm: number
  maxWidthMm: number
  crackDepthMm: number
  concreteCoverMm: number
  rebarClearanceMm: number
  orientation: string
  confidence: string
  ndtMethod: string
  calibrationStatus: string
  deteriorationType: string
  carbonationDepthMm: number
  rebarCondition: string
  severityStatus: 'Attention' | 'Critical' | 'Nominal'
  recommendedAction: string
  crackImage: string
}

export const COLUMN_C03_DEFECT: DefectDiagnosticTelemetry = {
  crackId: 'CRK-2026-C03-01',
  associatedAsset: 'Commercial Tower A (Civil ID: BLD-001)',
  associatedInspection: 'Q3 Structural Health Audit (INSP-2026-09)',
  componentId: 'COL-C03',
  componentName: 'Column C-03 (Perimeter Moment Frame)',
  gridLocation: 'Grid Line C / Axis 3',
  floorLevel: 'Floor 2 (Elevation +7.2m to +10.8m)',
  crackType: 'Diagonal Surface Shear Crack',
  lengthMm: 184,
  maxWidthMm: 0.8,
  crackDepthMm: 28,
  concreteCoverMm: 40,
  rebarClearanceMm: 12,
  orientation: 'Diagonal Shear, ~48° from horizontal',
  confidence: '94% (YOLO11-seg + Sub-pixel Edge Trace)',
  ndtMethod: 'Stereo Photogrammetry + Ultrasonic Pulse Echo (UPV)',
  calibrationStatus: 'Calibrated (0.24 mm/px @ 1.2m focal distance)',
  deteriorationType: 'Concrete cover micro-cracking & localized carbonation ingress',
  carbonationDepthMm: 22,
  rebarCondition: 'Stirrup tie at 12mm proximity; passive layer intact, ingress alert',
  severityStatus: 'Attention',
  recommendedAction: 'Apply epoxy-resin micro-injection within 30 days and install vibrating wire strain/crack gauge.',
  crackImage: '/crack-detail.jpg',
}

export interface StructuralMemberData {
  id: string
  name: string
  type: 'column' | 'beam' | 'slab' | 'core' | 'facade' | 'staircase' | 'penthouse' | 'foundation'
  level: string
  material: string
  dimensions: string
  designFunction: string
  statusType: 'monitored' | 'healthy' | 'attention' | 'critical'
  latestFinding?: string
  confidence?: string
  lengthPx?: string
  widthEst?: string
  depthEst?: string
  findingStatus?: string
  recommendedAction?: string
  crackImage?: string
  sensorMetric?: string
  sensorType?: string
}

export const BUILDING_MEMBERS: Record<string, StructuralMemberData> = {
  'COL-C03': {
    id: 'COL-C03',
    name: 'Column C-03',
    type: 'column',
    level: 'Floor 2 (F2, +7.2m)',
    material: 'Reinforced Concrete (Grade C50/60) with 8×Ø28mm Longitudinal Rebar',
    dimensions: '0.70m × 0.70m section × 3.6m floor height',
    designFunction: 'Primary perimeter moment frame column resisting combined axial load and lateral shear.',
    statusType: 'attention',
    latestFinding: 'Surface Shear Crack & Depth Penetration',
    confidence: '94%',
    lengthPx: '184 mm',
    widthEst: '0.8 mm',
    depthEst: '28 mm (Cover: 40 mm)',
    findingStatus: 'Attention',
    recommendedAction: 'Schedule close-up ultrasonic pulse echo (UPV) and install continuous crack-width telemetry.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Foil Resistance Strain Gauge Full-Bridge (SG-03)',
    sensorMetric: 'Axial Strain: 420 µε (Elastic threshold: 850 µε)',
  },
  'CORE-SHEAR-GF': {
    id: 'CORE-SHEAR-GF',
    name: 'Central Shear Wall Core',
    type: 'core',
    level: 'Continuous (GF - Roof)',
    material: 'Monolithic Reinforced Concrete Shear Wall (350mm thickness)',
    dimensions: '6.0m × 4.8m box core × 19.5m total height',
    designFunction: 'Primary lateral force-resisting system (drift control) and vertical elevator core.',
    statusType: 'healthy',
    latestFinding: 'Core Drift Nominal',
    confidence: '98%',
    lengthPx: '—',
    widthEst: '< 0.1 mm',
    depthEst: 'Nominal',
    findingStatus: 'Nominal',
    recommendedAction: 'Maintain baseline telemetry logging. No structural intervention required.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Dual-Axis High Precision Biaxial Inclinometer (TM-101)',
    sensorMetric: 'Lateral Drift Angle: 0.003° (Well within ±0.05° code limit)',
  },
  'SLAB-F2': {
    id: 'SLAB-F2',
    name: 'Floor Slab F2 (North Bay)',
    type: 'slab',
    level: 'Floor 2 (+7.2m)',
    material: 'Post-Tensioned Reinforced Concrete (Unbonded Monostrand)',
    dimensions: '18.0m span × 14.0m bay × 0.32m thickness',
    designFunction: 'Two-way flexural diaphragm distributing live floor loads to column capitals.',
    statusType: 'attention',
    latestFinding: 'Soffit Delamination & Carbonation Patch',
    confidence: '91%',
    lengthPx: '210 mm',
    widthEst: '0.35 mm',
    depthEst: '15 mm',
    findingStatus: 'Attention',
    recommendedAction: 'Perform phenolphthalein carbonation depth test on slab soffit.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Vibrating Wire Crackmeter (VW-02)',
    sensorMetric: 'Displacement Opening: 0.12 mm (Baseline stable)',
  },
  'BEAM-F2-MOMENT': {
    id: 'BEAM-F2-MOMENT',
    name: 'Floor 2 Perimeter Moment Girder',
    type: 'beam',
    level: 'Floor 2 (+7.2m)',
    material: 'Cast-in-Place High-Strength Concrete (Grade C45)',
    dimensions: '0.45m width × 0.55m depth × 6.0m span',
    designFunction: 'Transfers transverse floor shear and forms rigid ductile moment frame connection.',
    statusType: 'healthy',
    latestFinding: 'Deflection Nominal',
    confidence: '97%',
    lengthPx: '—',
    widthEst: 'Nominal',
    depthEst: 'Nominal',
    findingStatus: 'Nominal',
    recommendedAction: 'Standard periodic visual review cycle.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Fiber-Optic Distributed Strain Array (FBG-12)',
    sensorMetric: 'Midspan Sag: 1.8 mm (Allowable: 16.0 mm / L/360)',
  },
  'STAIR-CENTRAL': {
    id: 'STAIR-CENTRAL',
    name: 'Internal Egress Staircase',
    type: 'staircase',
    level: 'Inter-Level Circulation (GF - Roof)',
    material: 'Precast Reinforced Concrete Treads & Landings on Steel Stringers',
    dimensions: 'Dog-leg dual flight stairs, 1.4m tread width',
    designFunction: 'Vertical egress and emergency evacuation staircase within the central core.',
    statusType: 'healthy',
    latestFinding: 'Vibration Class A',
    confidence: '97%',
    lengthPx: '—',
    widthEst: 'Nominal',
    depthEst: 'Nominal',
    findingStatus: 'Nominal',
    recommendedAction: 'Routine facility safety audit.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Low-Frequency Accelerometer (ACC-08)',
    sensorMetric: 'Footfall Dynamic RMS: 0.03 m/s²',
  },
  'ENTRANCE-PAVILION': {
    id: 'ENTRANCE-PAVILION',
    name: 'Ground Floor Entrance Pavilion',
    type: 'facade',
    level: 'Ground Floor (GF)',
    material: 'Structural Steel Framing with Point-Fixed Architectural Glazing',
    dimensions: '6.0m × 4.5m × 3.5m canopy projection',
    designFunction: 'Weather canopy, reception lobby, and building entrance transition.',
    statusType: 'healthy',
    latestFinding: 'Glazing Seals Intact',
    confidence: '95%',
    lengthPx: '—',
    widthEst: 'Nominal',
    depthEst: 'Nominal',
    findingStatus: 'Nominal',
    recommendedAction: 'Routine sealant inspection.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Laser Displacement Sensor (LDS-01)',
    sensorMetric: 'Thermal Expansion: 1.2 mm',
  },
  'ROOF-PENTHOUSE': {
    id: 'ROOF-PENTHOUSE',
    name: 'Roof Structure & Parapet',
    type: 'penthouse',
    level: 'Roof Level (+18.0m)',
    material: 'Reinforced Concrete Parapet & Steel Mechanical Enclosure',
    dimensions: '18.0m × 14.0m perimeter with 1.2m parapet',
    designFunction: 'Roof drainage, perimeter fall protection, and mechanical plant enclosure.',
    statusType: 'healthy',
    latestFinding: 'Waterproofing Sound',
    confidence: '98%',
    lengthPx: '—',
    widthEst: 'Nominal',
    depthEst: 'Nominal',
    findingStatus: 'Nominal',
    recommendedAction: 'Standard biannual roof membrane check.',
    crackImage: '/crack-detail.jpg',
    sensorType: 'Moisture Transducer (MT-02)',
    sensorMetric: 'Membrane Relative Humidity: 32%',
  },
}

export const FLOOR_ELEVATIONS: Record<BuildingFloor, number> = {
  Roof: 18.0,
  F4: 14.4,
  F3: 10.8,
  F2: 7.2,
  F1: 3.6,
  GF: 0.0,
}
