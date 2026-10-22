/**
 * Industrial Campus Demonstration Data
 * High-fidelity structural digital twin data for the homepage 3D interactive hero.
 * Perfectly calibrated with cinematic architectural visualization standards.
 */

export type MonitoringMode = 'structure' | 'monitoring' | 'defects'

export interface CampusStructureMarker {
  id: string
  name: string
  secondaryLabel: string
  category: string
  statusText: string
  statusType: 'monitored' | 'healthy' | 'attention' | 'critical'
  latestFinding: string
  confidence: string
  lengthPx: string
  findingStatus: string
  findingStatusColor: 'yellow' | 'green' | 'orange' | 'red'
  // 2D Normalized Screen Position percentages for ultra-realistic cinematic layer
  screenPos: {
    top: string
    left: string
    lineHeight: string
    labelPlacement?: 'right' | 'left'
  }
  // 3D scene world coordinates
  worldPos: [number, number, number]
  sensorName: string
  sensorType: string
  telemetryMetric: string
  defectTitle: string
  defectSeverity: 'minor' | 'moderate' | 'critical'
  defectMeasurements: string
  recommendedAction: string
  crackImage: string
}

export const CAMPUS_MARKERS: CampusStructureMarker[] = [
  {
    id: 'production_hall',
    name: 'Production Hall',
    secondaryLabel: 'Structure · Monitoring',
    category: 'Industrial Building',
    statusText: 'Monitored',
    statusType: 'monitored',
    latestFinding: 'Surface Crack',
    confidence: '92%',
    lengthPx: '184',
    findingStatus: 'Needs Review',
    findingStatusColor: 'yellow',
    screenPos: {
      top: '42%',
      left: '51.5%',
      lineHeight: '62px',
      labelPlacement: 'right',
    },
    worldPos: [1.5, 3.2, -6.5],
    sensorName: 'Vibration & Acoustic Array ACC-204',
    sensorType: 'Triaxial Seismic Accelerometer (500 Hz)',
    telemetryMetric: 'RMS Vibration: 1.84 mm/s · Frequency: 14.2 Hz',
    defectTitle: 'Longitudinal Surface Shear Crack',
    defectSeverity: 'moderate',
    defectMeasurements: 'Length: 184 px (92 mm) · Width: 0.38 mm · Depth: 14 mm',
    recommendedAction: 'Schedule close-up ultrasonic testing (UT) and crack-width monitoring gauge installation within 30 days.',
    crackImage: '/crack-detail.jpg',
  },
  {
    id: 'processing_unit',
    name: 'Processing Unit',
    secondaryLabel: 'Structure · Monitoring',
    category: 'Petrochemical Refinement Facility',
    statusText: 'Monitored',
    statusType: 'monitored',
    latestFinding: 'Thermal Gradient Variance',
    confidence: '94%',
    lengthPx: '82',
    findingStatus: 'Needs Review',
    findingStatusColor: 'yellow',
    screenPos: {
      top: '14%',
      left: '43.5%',
      lineHeight: '54px',
      labelPlacement: 'right',
    },
    worldPos: [11.5, 6.0, -7.5],
    sensorName: 'High-Temp Thermocouple Array TC-3',
    sensorType: 'Type-K Mineral Insulated Telemetry',
    telemetryMetric: 'Operating Temp: 142°C · Delta: +4.2°C vs Baseline',
    defectTitle: 'Localized Thermal Insulation Flaw',
    defectSeverity: 'minor',
    defectMeasurements: 'Length: 82 px (41 mm) · Area: 120 cm²',
    recommendedAction: 'Inspect thermal insulation cladding wrap during scheduled quarterly turnaround.',
    crackImage: '/crack-detail.jpg',
  },
  {
    id: 'storage_tanks',
    name: 'Storage Tanks',
    secondaryLabel: 'Structure · Inspection',
    category: 'Fluid Storage Facility',
    statusText: 'Monitored',
    statusType: 'monitored',
    latestFinding: 'Foundation Micro-Cracking',
    confidence: '89%',
    lengthPx: '126',
    findingStatus: 'Needs Review',
    findingStatusColor: 'yellow',
    screenPos: {
      top: '26%',
      left: '15.5%',
      lineHeight: '50px',
      labelPlacement: 'right',
    },
    worldPos: [10.5, 4.0, 5.5],
    sensorName: 'Acoustic Emission Probe AE-04',
    sensorType: '150 kHz Resonant Acoustic Transducer',
    telemetryMetric: 'Hit Rate: 8 hits/hr · Baseline nominal',
    defectTitle: 'Concrete Ring-Beam Efflorescence & Spalling',
    defectSeverity: 'moderate',
    defectMeasurements: 'Length: 126 px (63 mm) · Depth: 18 mm',
    recommendedAction: 'Apply concrete penetrant sealer and repair spalled perimeter berm lip.',
    crackImage: '/crack-detail.jpg',
  },
  {
    id: 'administration',
    name: 'Administration',
    secondaryLabel: 'Structure · Inspection',
    category: 'Corporate Office & Control',
    statusText: 'Monitored',
    statusType: 'healthy',
    latestFinding: 'Curtain Wall Seal Nominal',
    confidence: '96%',
    lengthPx: '—',
    findingStatus: 'Nominal',
    findingStatusColor: 'green',
    screenPos: {
      top: '64%',
      left: '71%',
      lineHeight: '46px',
      labelPlacement: 'right',
    },
    worldPos: [-9.0, 2.5, 5.5],
    sensorName: 'Dual-Axis Optical Tiltmeter TM-101',
    sensorType: 'High-Precision Biaxial Inclinometer',
    telemetryMetric: 'Tilt Angle: 0.003° (Well within ±0.05° limit)',
    defectTitle: 'No Active Structural Anomalies',
    defectSeverity: 'minor',
    defectMeasurements: 'All structural members within elastic tolerance limits.',
    recommendedAction: 'Maintain standard annual visual survey schedule.',
    crackImage: '/crack-detail.jpg',
  },
  {
    id: 'utility_building',
    name: 'Utility Building',
    secondaryLabel: 'Structure · Assessment',
    category: 'Infrastructure & Energy',
    statusText: 'Monitored',
    statusType: 'attention',
    latestFinding: 'Expansion Joint Wear',
    confidence: '91%',
    lengthPx: '110',
    findingStatus: 'Needs Review',
    findingStatusColor: 'yellow',
    screenPos: {
      top: '45.5%',
      left: '88%',
      lineHeight: '58px',
      labelPlacement: 'left',
    },
    worldPos: [-6.0, 2.2, -8.0],
    sensorName: 'Joint Crackmeter LVDT-10',
    sensorType: 'Vibrating Wire Displacement Gauge',
    telemetryMetric: 'Expansion Joint Gap: 14.8 mm (Design Limit: 20 mm)',
    defectTitle: 'Expansion Joint Sealant Deterioration',
    defectSeverity: 'moderate',
    defectMeasurements: 'Length: 110 px (55 mm) · Gap: 4 mm',
    recommendedAction: 'Replace weatherstrip elastomeric seal and re-torque stainless steel retainer bolts.',
    crackImage: '/crack-detail.jpg',
  },
]
