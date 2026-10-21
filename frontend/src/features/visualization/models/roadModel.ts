import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildRoadModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  // Check for completed inspections with findings
  const latestInspection = inspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(latestInspection)

  // Standard engineering materials
  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A',
    roughness: 0.35,
    metalness: 0.25,
  })
  const matNominal = new THREE.MeshStandardMaterial({
    color: '#B6BDA8',
    roughness: 0.5,
    metalness: 0.2,
  })
  const matNotAssessed = new THREE.MeshStandardMaterial({
    color: '#414039',
    roughness: 0.65,
    metalness: 0.1,
  })
  const matConcrete = new THREE.MeshStandardMaterial({
    color: '#525048',
    roughness: 0.75,
    metalness: 0.1,
  })
  const matAsphalt = new THREE.MeshStandardMaterial({
    color: '#282724',
    roughness: 0.9,
    metalness: 0.05,
  })
  const matBarrier = new THREE.MeshStandardMaterial({
    color: '#737064',
    roughness: 0.5,
    metalness: 0.3,
  })
  const matBearings = new THREE.MeshStandardMaterial({
    color: '#1C1B19',
    roughness: 0.4,
    metalness: 0.4,
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

  // ── 1. End Abutments & Sloped Wing Walls ─────────────────────────────────
  const abutmentPositions = [-17, 17]
  abutmentPositions.forEach((x, idx) => {
    const isWest = idx === 0
    const abutmentId = isWest ? 'ABUTMENT-WEST' : 'ABUTMENT-EAST'

    const abutGeo = new THREE.BoxGeometry(3.6, 5.0, 7.5)
    const abutMesh = new THREE.Mesh(abutGeo)
    abutMesh.position.set(x, 2.5, 0)
    registerMesh(
      abutMesh,
      {
        id: abutmentId,
        name: isWest ? 'West Approach Abutment' : 'East Approach Abutment',
        type: 'abutment',
        material: asset.material || 'Reinforced Concrete (Grade C35)',
        status: 'not_assessed',
        designFunction: 'Transfers end span live loads to embankment subsoil and retains approach fill',
        dimensions: '3.6m × 5.0m × 7.5m',
      },
      matConcrete
    )

    // Sloped wing walls (lateral embankment retention)
    const wingGeo = new THREE.BoxGeometry(4.0, 3.2, 0.6)
    const wingMeshNorth = new THREE.Mesh(wingGeo)
    wingMeshNorth.position.set(x + (isWest ? -1.0 : 1.0), 1.6, 3.8)
    wingMeshNorth.rotation.y = isWest ? -0.25 : 0.25
    registerMesh(
      wingMeshNorth,
      {
        id: `${abutmentId}-WING-N`,
        name: `${isWest ? 'West' : 'East'} Abutment North Wing Wall`,
        type: 'retaining_wall',
        material: 'Reinforced Concrete',
        status: 'not_assessed',
        designFunction: 'Lateral retention of motorway embankment approach fill',
        dimensions: '4.0m × 3.2m × 0.6m',
      },
      matNotAssessed
    )
  })

  // ── 2. Intermediate Hammerhead Pier Bents ────────────────────────────────
  const pierXPositions = [-6, 6]
  pierXPositions.forEach((px, pIdx) => {
    const pierId = `PIER-BENT-${pIdx + 1}`

    // Foundation footing
    const footingGeo = new THREE.BoxGeometry(4.5, 1.2, 4.5)
    const footingMesh = new THREE.Mesh(footingGeo)
    footingMesh.position.set(px, 0.6, 0)
    registerMesh(
      footingMesh,
      {
        id: `${pierId}-FOOTING`,
        name: `Pier ${pIdx + 1} Spread Foundation Footing`,
        type: 'pier',
        material: 'Reinforced Concrete',
        status: 'assessed_nominal',
        designFunction: 'Distributes axial and overturning reactions to deep foundation piling',
        dimensions: '4.5m × 1.2m × 4.5m',
      },
      matNominal
    )

    // Cylindrical pier column shaft
    const columnGeo = new THREE.CylinderGeometry(1.3, 1.5, 4.2, 24)
    const columnMesh = new THREE.Mesh(columnGeo)
    columnMesh.position.set(px, 3.2, 0)
    registerMesh(
      columnMesh,
      {
        id: `${pierId}-COLUMN`,
        name: `Pier ${pIdx + 1} Cylindrical Column Shaft`,
        type: 'pier',
        material: 'Reinforced Concrete (Grade C40)',
        status: 'assessed_nominal',
        designFunction: 'Primary compression member transferring continuous deck reaction',
        dimensions: 'Diameter 2.8m × Height 4.2m',
      },
      matNominal
    )

    // Hammerhead crosshead beam (cantilevered pier cap)
    const capGeo = new THREE.BoxGeometry(2.8, 1.1, 7.6)
    const capMesh = new THREE.Mesh(capGeo)
    capMesh.position.set(px, 5.75, 0)
    registerMesh(
      capMesh,
      {
        id: `CROSSHEAD-${pIdx + 1}`,
        name: `Pier ${pIdx + 1} Hammerhead Cantilever Crosshead`,
        type: 'crosshead',
        material: 'Prestressed Concrete Crosshead',
        status: 'assessed_nominal',
        designFunction: 'Cantilever cap supporting elastomeric bearings and multi-cell box girders',
        dimensions: '2.8m × 1.1m × 7.6m',
      },
      matNominal
    )

    // Elastomeric bearing pads
    ;[-2.4, 0, 2.4].forEach((bz, bIdx) => {
      const padGeo = new THREE.BoxGeometry(0.8, 0.25, 0.8)
      const padMesh = new THREE.Mesh(padGeo)
      padMesh.position.set(px, 6.4, bz)
      registerMesh(
        padMesh,
        {
          id: `BEARING-${pIdx + 1}-${bIdx + 1}`,
          name: `Pier ${pIdx + 1} Bearing Pad ${bIdx + 1}`,
          type: 'bearing',
          material: 'Neoprene Elastomeric Bearing with Steel Shims',
          status: 'not_assessed',
          designFunction: 'Accommodates longitudinal thermal articulation and seismic vibration damping',
          dimensions: '0.8m × 0.25m × 0.8m',
        },
        matBearings
      )
    })
  })

  // ── 3. Continuous Prestressed Concrete Box Girders & Deck Soffits ─────────
  const spans = [
    { id: 'SOFFIT-SPAN-1', name: 'Span 1 Soffit (West Approach)', x: -11.5, length: 11.0, isMidspan: false },
    { id: 'SOFFIT-SPAN-2', name: 'Span 2 Midspan Soffit & Box Girder', x: 0, length: 12.0, isMidspan: true },
    { id: 'SOFFIT-SPAN-3', name: 'Span 3 Soffit (East Approach)', x: 11.5, length: 11.0, isMidspan: false },
  ]

  spans.forEach((span) => {
    const isTargetMidspan = span.isMidspan && hasFindings
    const girderMat = isTargetMidspan ? matFindings : matNominal

    const boxGeo = new THREE.BoxGeometry(span.length - 0.2, 1.4, 5.6)
    const boxMesh = new THREE.Mesh(boxGeo)
    boxMesh.position.set(span.x, 7.2, 0)

    registerMesh(
      boxMesh,
      {
        id: span.id,
        name: span.name,
        type: 'girder',
        material: asset.material || 'Prestressed Concrete (Grade C50/60)',
        status: isTargetMidspan ? 'assessed_findings' : 'assessed_nominal',
        designFunction: 'Primary longitudinal flexural box girder resisting traffic live loads and hogging moments',
        dimensions: `${span.length}m × 1.4m × 5.6m`,
        defectSummary: isTargetMidspan
          ? `${latestInspection?.defect_count} structural hairline flexural crack(s) observed at midspan soffit via elevated platform inspection.`
          : undefined,
        findingsCount: isTargetMidspan ? latestInspection?.defect_count : 0,
        linkedEvidencePaths: isTargetMidspan
          ? [
              '/uploads/evidence/m25_j14_flyover_approach.jpg',
              '/uploads/evidence/m25_j14_terminal5_sliproad_pier.jpg',
              '/uploads/evidence/m25_j14_interchange_gantry_superstructure.jpg',
            ]
          : undefined,
      },
      girderMat
    )
  })

  // ── 4. Continuous Carriageway Deck Slab & Asphalt Road Surface ────────────
  const deckLength = 34.0
  const deckWidth = 7.4
  const deckGeo = new THREE.BoxGeometry(deckLength, 0.45, deckWidth)
  const deckMesh = new THREE.Mesh(deckGeo)
  deckMesh.position.set(0, 8.1, 0)
  registerMesh(
    deckMesh,
    {
      id: 'ROAD-DECK-SLAB',
      name: 'Continuous Highway Carriageway Deck Slab',
      type: 'deck',
      material: 'Prestressed Concrete Deck with Waterproofing Membrane',
      status: 'assessed_nominal',
      designFunction: 'Carries motorway traffic load and distributes wheel shear to box girder webs',
      dimensions: `${deckLength}m × 0.45m × ${deckWidth}m`,
    },
    matNominal
  )

  // Asphalt wearing course
  const asphaltGeo = new THREE.BoxGeometry(deckLength - 0.2, 0.08, deckWidth - 0.8)
  const asphaltMesh = new THREE.Mesh(asphaltGeo)
  asphaltMesh.position.set(0, 8.36, 0)
  registerMesh(
    asphaltMesh,
    {
      id: 'ASPHALT-SURFACE',
      name: 'Asphalt Concrete Wearing Course',
      type: 'deck',
      material: 'Dense Bituminous Macadam (DBM 50mm)',
      status: 'illustrative',
      designFunction: 'Friction wearing surface and structural deck weatherproofing',
      dimensions: `${deckLength - 0.2}m × 0.08m × ${deckWidth - 0.8}m`,
    },
    matAsphalt
  )

  // ── 5. Concrete Crash Parapets & Highway Barriers ─────────────────────────
  ;[-3.5, 3.5].forEach((pz, pIdx) => {
    const isNorth = pIdx === 0
    const parapetGeo = new THREE.BoxGeometry(deckLength, 0.85, 0.35)
    const parapetMesh = new THREE.Mesh(parapetGeo)
    parapetMesh.position.set(0, 8.75, pz)
    registerMesh(
      parapetMesh,
      {
        id: isNorth ? 'PARAPET-NORTH' : 'PARAPET-SOUTH',
        name: isNorth ? 'North Highway Crash Barrier Parapet' : 'South Highway Crash Barrier Parapet',
        type: 'parapet',
        material: 'Reinforced Concrete Parapet (BS 6779 / EN 1317 H4a)',
        status: 'not_assessed',
        designFunction: 'Vehicle impact containment barrier and edge drainage gutter',
        dimensions: `${deckLength}m × 0.85m × 0.35m`,
      },
      matBarrier
    )
  })

  return {
    group,
    components,
    modelType: 'Highway Flyover Bridge',
    isIllustrative: true,
  }
}
