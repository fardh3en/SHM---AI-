import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildDamModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  // Check for completed inspections with findings
  const latestInspection = inspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(latestInspection)

  // Standard engineering materials for Victorian masonry dam / reservoir intake
  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A',
    roughness: 0.5,
    metalness: 0.15,
  })
  const matNominal = new THREE.MeshStandardMaterial({
    color: '#B6BDA8',
    roughness: 0.6,
    metalness: 0.15,
  })
  const matBrickMasonry = new THREE.MeshStandardMaterial({
    color: '#8A5241', // Victorian red engineering brick
    roughness: 0.85,
    metalness: 0.05,
  })
  const matStoneAshlar = new THREE.MeshStandardMaterial({
    color: '#A8A495', // Portland limestone / sandstone coping
    roughness: 0.7,
    metalness: 0.1,
  })
  const matCastIron = new THREE.MeshStandardMaterial({
    color: '#2A2E33', // Victorian cast iron sluice gates
    roughness: 0.45,
    metalness: 0.65,
  })
  const matEmbankment = new THREE.MeshStandardMaterial({
    color: '#47533B', // Earth / turf covered reservoir embankment
    roughness: 0.95,
    metalness: 0.02,
  })
  const matWaterSill = new THREE.MeshStandardMaterial({
    color: '#2F4858',
    roughness: 0.3,
    metalness: 0.3,
    transparent: true,
    opacity: 0.75,
  })

  const registerMesh = (
    mesh: THREE.Mesh,
    data: StructuralComponentData,
    material: THREE.Material
  ) => {
    mesh.material = material
    mesh.userData = data
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)
    components.set(data.id, data)
  }

  // ── 1. Heavy Masonry Intake Retaining Headwalls ──────────────────────────
  // North Headwall (Inspected - has findings: mortar deterioration & efflorescence)
  const northWallMat = hasFindings ? matFindings : matNominal
  const headwallNorthGeo = new THREE.BoxGeometry(10.0, 6.5, 2.2)
  const headwallNorthMesh = new THREE.Mesh(headwallNorthGeo)
  headwallNorthMesh.position.set(-6.5, 3.25, 0)
  registerMesh(
    headwallNorthMesh,
    {
      id: 'NORTH-INTAKE-HEADWALL',
      name: 'North Reservoir Intake Retaining Headwall',
      type: 'retaining_wall',
      material: asset.material || 'Victorian Engineering Brick Masonry with Lime Mortar',
      status: hasFindings ? 'assessed_findings' : 'assessed_nominal',
      designFunction: 'Primary earth and water retention headwall resisting reservoir hydrostatic surcharge',
      dimensions: '10.0m × 6.5m × 2.2m',
      defectSummary: hasFindings
        ? `${latestInspection?.defect_count} defect(s): Mortar joint deterioration on north face; efflorescence visible at seepage points.`
        : undefined,
      findingsCount: hasFindings ? latestInspection?.defect_count : 0,
      linkedEvidencePaths: hasFindings
        ? [
            '/uploads/evidence/brixton_reservoir_lambeth_works.jpg',
            '/uploads/evidence/covered_reservoir_brick_retaining_wall.jpg',
            '/uploads/evidence/lambeth_waterworks_gate_headwall.jpg',
          ]
        : undefined,
    },
    northWallMat
  )

  // South Headwall (Nominal)
  const headwallSouthGeo = new THREE.BoxGeometry(10.0, 6.5, 2.2)
  const headwallSouthMesh = new THREE.Mesh(headwallSouthGeo)
  headwallSouthMesh.position.set(6.5, 3.25, 0)
  registerMesh(
    headwallSouthMesh,
    {
      id: 'SOUTH-INTAKE-HEADWALL',
      name: 'South Reservoir Intake Retaining Headwall',
      type: 'retaining_wall',
      material: 'Victorian Engineering Brick Masonry',
      status: 'assessed_nominal',
      designFunction: 'Lateral reservoir retention wing wall and intake approach training structure',
      dimensions: '10.0m × 6.5m × 2.2m',
    },
    matNominal
  )

  // Ashlar Stone Coping Course (Top perimeter)
  const copingGeo = new THREE.BoxGeometry(24.0, 0.45, 2.6)
  const copingMesh = new THREE.Mesh(copingGeo)
  copingMesh.position.set(0, 6.72, 0)
  registerMesh(
    copingMesh,
    {
      id: 'COPING-STONE-COURSE',
      name: 'Dressed Ashlar Stone Coping Course',
      type: 'weir_crest',
      material: 'Dressed Portland Limestone Coping',
      status: 'not_assessed',
      designFunction: 'Weather capping and parapet wash shedding surface run-off from wall core',
      dimensions: '24.0m × 0.45m × 2.6m',
    },
    matStoneAshlar
  )

  // ── 2. Twin Intake Arch Culvert Portals ──────────────────────────────────
  ;[-2.2, 2.2].forEach((cx, cIdx) => {
    const portalId = `CULVERT-PORTAL-${cIdx + 1}`

    // Outer arch portal voussoir band
    const portalGeo = new THREE.TorusGeometry(1.6, 0.35, 12, 24, Math.PI)
    const portalMesh = new THREE.Mesh(portalGeo)
    portalMesh.position.set(cx, 1.8, 1.15)
    portalMesh.rotation.z = Math.PI
    registerMesh(
      portalMesh,
      {
        id: portalId,
        name: `Inlet Arch Culvert Portal ${cIdx + 1}`,
        type: 'culvert_portal',
        material: 'Radial Gauged Brick Masonry Arch',
        status: 'assessed_nominal',
        designFunction: 'Compression arch distributing surcharge around twin intake conduits',
        dimensions: 'Span 3.2m × Height 2.2m',
      },
      matBrickMasonry
    )

    // Cast-iron sluice penstock gate
    const gateGeo = new THREE.BoxGeometry(2.4, 2.2, 0.25)
    const gateMesh = new THREE.Mesh(gateGeo)
    gateMesh.position.set(cx, 1.4, 0.2)
    registerMesh(
      gateMesh,
      {
        id: `SLUICE-GATE-${cIdx + 1}`,
        name: `Cast-Iron Intake Sluice Penstock ${cIdx + 1}`,
        type: 'sluice_gate',
        material: 'Victorian Grey Cast Iron (Grade 220)',
        status: 'assessed_nominal',
        designFunction: 'Adjustable penstock regulating volumetric inflow to service reservoir cells',
        dimensions: '2.4m × 2.2m × 0.25m',
      },
      matCastIron
    )

    // Vertical valve spindle & lifting stem
    const stemGeo = new THREE.CylinderGeometry(0.08, 0.08, 4.8, 12)
    const stemMesh = new THREE.Mesh(stemGeo)
    stemMesh.position.set(cx, 4.4, 0.2)
    registerMesh(
      stemMesh,
      {
        id: `VALVE-SPINDLE-${cIdx + 1}`,
        name: `Sluice Operating Spindle & Gear Stem ${cIdx + 1}`,
        type: 'sluice_gate',
        material: 'Wrought Iron Actuator Shaft',
        status: 'not_assessed',
        designFunction: 'Mechanical spindle transmitting manual capstan torque to penstock slide',
        dimensions: 'Diameter 0.16m × Height 4.8m',
      },
      matCastIron
    )

    // Coarse intake trash rack screen
    const screenGeo = new THREE.BoxGeometry(2.6, 2.4, 0.1)
    const screenMesh = new THREE.Mesh(screenGeo)
    screenMesh.position.set(cx, 1.3, 1.9)
    registerMesh(
      screenMesh,
      {
        id: `INTAKE-SCREEN-${cIdx + 1}`,
        name: `Coarse Intake Trash Rack Screen ${cIdx + 1}`,
        type: 'intake_screen',
        material: 'Forged Steel Trash Rack Bar Grid',
        status: 'not_assessed',
        designFunction: 'Intercepts large floating debris before culvert tunnel intake',
        dimensions: '2.6m × 2.4m × 0.1m',
      },
      matCastIron
    )
  })

  // ── 3. Central Overflow Weir Crest & Discharge Apron ─────────────────────
  const weirGeo = new THREE.BoxGeometry(3.0, 1.8, 3.2)
  const weirMesh = new THREE.Mesh(weirGeo)
  weirMesh.position.set(0, 0.9, -1.0)
  registerMesh(
    weirMesh,
    {
      id: 'WEIR-SPILLWAY-CREST',
      name: 'Central Spillway Overflow Weir Crest',
      type: 'weir_crest',
      material: 'Granite Ashlar Weir Lip and Concrete Apron',
      status: 'not_assessed',
      designFunction: 'Controls maximum reservoir pool elevation and safely discharges flood excess',
      dimensions: '3.0m × 1.8m × 3.2m',
    },
    matStoneAshlar
  )

  // Forebay intake pool water surface
  const waterGeo = new THREE.BoxGeometry(18.0, 0.15, 6.0)
  const waterMesh = new THREE.Mesh(waterGeo)
  waterMesh.position.set(0, 0.75, 4.0)
  registerMesh(
    waterMesh,
    {
      id: 'FOREBAY-WATER-POOL',
      name: 'Intake Forebay Water Sill',
      type: 'deck',
      material: 'Hydraulic Water Datum Plane',
      status: 'illustrative',
      designFunction: 'Visual hydraulic reference plane for operational intake water level',
      dimensions: '18.0m × 0.15m × 6.0m',
    },
    matWaterSill
  )

  // ── 4. Sloped Embankment Buttress Slopes ──────────────────────────────────
  ;[-14.5, 14.5].forEach((ex, eIdx) => {
    const isWest = eIdx === 0
    const embGeo = new THREE.ConeGeometry(5.2, 6.0, 4)
    const embMesh = new THREE.Mesh(embGeo)
    embMesh.position.set(ex, 3.0, 0)
    embMesh.rotation.y = Math.PI / 4
    registerMesh(
      embMesh,
      {
        id: isWest ? 'EMBANKMENT-WEST' : 'EMBANKMENT-EAST',
        name: isWest ? 'West Berm Earth Embankment' : 'East Berm Earth Embankment',
        type: 'embankment',
        material: 'Compacted Clay Core with Turf Vegetated Topsoil',
        status: 'not_assessed',
        designFunction: 'Earth embankment providing lateral containment for covered reservoir boundary',
        dimensions: 'Base 7.4m × Height 6.0m',
      },
      matEmbankment
    )
  })

  return {
    group,
    components,
    modelType: 'Reservoir Inlet Structure',
    isIllustrative: true,
  }
}
