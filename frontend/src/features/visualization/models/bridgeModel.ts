import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData, ComponentStatus } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildBridgeModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  const isBrooklyn = asset.name.toLowerCase().includes('brooklyn')
  const isGGB = asset.name.toLowerCase().includes('golden gate')

  // Find any inspection findings for the asset
  const latestInspection = inspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(latestInspection)

  // Color materials
  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A', // Crimson alert
    roughness: 0.35,
    metalness: 0.3,
  })
  const matNominal = new THREE.MeshStandardMaterial({
    color: '#B6BDA8', // Sage nominal
    roughness: 0.45,
    metalness: 0.2,
  })
  const matNotAssessed = new THREE.MeshStandardMaterial({
    color: '#414039', // Dark slate unassessed
    roughness: 0.6,
    metalness: 0.1,
  })
  const matConcrete = new THREE.MeshStandardMaterial({
    color: '#55544D',
    roughness: 0.8,
    metalness: 0.05,
  })

  // Helper to add a tagged mesh
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

  // ── 1. Substructure Piers ─────────────────────────────────────────────────
  const pierPositions = [-12, 0, 12]
  pierPositions.forEach((x, idx) => {
    const isSplashZonePier = isGGB && idx === 0
    const pierStatus: ComponentStatus = isSplashZonePier && hasFindings
      ? 'assessed_findings'
      : isSplashZonePier
      ? 'assessed_nominal'
      : 'not_assessed'

    const pierMat = pierStatus === 'assessed_findings'
      ? matFindings
      : pierStatus === 'assessed_nominal'
      ? matNominal
      : matConcrete

    // Foundation footing / Caisson
    const footingGeo = new THREE.BoxGeometry(4.5, 2.5, 5.5)
    const footingMesh = new THREE.Mesh(footingGeo)
    footingMesh.position.set(x, -2, 0)
    registerMesh(
      footingMesh,
      {
        id: `PIER-FOOTING-${idx + 1}`,
        name: idx === 0 ? 'North Pier Foundation Footing' : `Pier ${idx + 1} Substructure Footing`,
        type: 'pier',
        material: asset.material || 'Reinforced Concrete (Grade C45)',
        status: pierStatus,
        designFunction: 'Carries axial bridge load to bedrock anchorage caisson',
        dimensions: '4.5m × 2.5m × 5.5m',
        defectSummary: isSplashZonePier && hasFindings
          ? `${latestInspection?.defect_count} structural defect(s) detected in tidal splash zone.`
          : undefined,
        findingsCount: isSplashZonePier ? latestInspection?.defect_count : 0,
        linkedEvidencePaths: isSplashZonePier
          ? ['/uploads/evidence/ggb_marin_tower_substructure.jpg', '/uploads/evidence/ggb_north_pier_lime_point.jpg']
          : undefined,
      },
      pierMat
    )

    // Vertical pier shaft
    const pierGeo = new THREE.CylinderGeometry(1.4, 1.6, 5, 16)
    const pierMesh = new THREE.Mesh(pierGeo)
    pierMesh.position.set(x, 1.5, 0)
    registerMesh(
      pierMesh,
      {
        id: `PIER-SHAFT-${idx + 1}`,
        name: idx === 0 ? 'North Pier Shaft Column' : `Pier Shaft ${idx + 1}`,
        type: 'pier',
        material: asset.material || 'Reinforced Concrete',
        status: pierStatus,
        designFunction: 'Vertical compression member transmitting deck reactions',
        dimensions: 'Diameter 3.0m × Height 5.0m',
      },
      pierMat
    )

    // Bearing crosshead / shelf
    const shelfGeo = new THREE.BoxGeometry(3.5, 0.8, 4.2)
    const shelfMesh = new THREE.Mesh(shelfGeo)
    shelfMesh.position.set(x, 4.2, 0)
    registerMesh(
      shelfMesh,
      {
        id: `BEARING-SHELF-${idx + 1}`,
        name: `Elastomeric Bearing Shelf Pier ${idx + 1}`,
        type: 'bearing',
        material: 'Neoprene elastomeric pads with steel shims',
        status: 'not_assessed',
        designFunction: 'Thermal expansion articulation and load transfer',
      },
      matNotAssessed
    )
  })

  // ── 2. Deck Slabs & Longitudinal Box Girders ─────────────────────────────
  const deckLength = 32
  const deckWidth = 4.8
  const deckGeo = new THREE.BoxGeometry(deckLength, 0.6, deckWidth)
  const deckMesh = new THREE.Mesh(deckGeo)
  deckMesh.position.set(0, 4.8, 0)
  registerMesh(
    deckMesh,
    {
      id: 'DECK-MAIN-SLAB',
      name: 'Main Deck Running Slab & Soffit',
      type: 'deck',
      material: 'Post-tensioned reinforced concrete slab with asphalt overlay',
      status: 'not_assessed',
      designFunction: 'Distributes live vehicular traffic across longitudinal girder spans',
      dimensions: '32m × 4.8m × 0.6m',
    },
    matNotAssessed
  )

  // ── 3. Truss Superstructure or Suspension Arch ───────────────────────────
  if (isBrooklyn) {
    // Gothic Arch Style Tower Framing
    const archH = 10
    const towerGeo = new THREE.BoxGeometry(3.5, archH, 2.5)
    const towerMesh = new THREE.Mesh(towerGeo)
    towerMesh.position.set(0, 9.8, 0)
    registerMesh(
      towerMesh,
      {
        id: 'TOWER-ARCH-MASONRY',
        name: 'Gothic Masonry Arch Tower',
        type: 'arch_voussoir',
        material: 'Granite ashlar masonry with Rosendale natural cement mortar',
        status: hasFindings ? 'assessed_findings' : 'assessed_nominal',
        designFunction: 'Primary suspension cable saddle support and main span anchor',
        dimensions: '3.5m × 10.0m × 2.5m',
        linkedEvidencePaths: [
          '/uploads/evidence/brooklyn_bridge_gothic_arch.jpg',
          '/uploads/evidence/brooklyn_bridge_tower_masonry_elevation.jpg',
        ],
      },
      hasFindings ? matFindings : matNominal
    )
  } else {
    // Continuous Steel Pratt Truss Superstructure
    const bays = 8
    const bayWidth = deckLength / bays
    const trussHeight = 4.2
    const zOffsets = [-deckWidth / 2, deckWidth / 2]

    zOffsets.forEach((z, sideIdx) => {
      const sideName = sideIdx === 0 ? 'Left' : 'Right'

      for (let i = 0; i < bays; i++) {
        const x1 = -deckLength / 2 + i * bayWidth
        const x2 = x1 + bayWidth
        const xm = (x1 + x2) / 2

        // Top chord
        const tcGeo = new THREE.BoxGeometry(bayWidth, 0.25, 0.25)
        const tcMesh = new THREE.Mesh(tcGeo)
        tcMesh.position.set(xm, 4.8 + trussHeight, z)
        registerMesh(
          tcMesh,
          {
            id: `TRUSS-TOP-${sideName.toUpperCase()}-${i + 1}`,
            name: `${sideName} Truss Top Chord Bay ${i + 1}`,
            type: 'chord_top',
            material: 'Structural Steel A572 Grade 50',
            status: 'not_assessed',
            designFunction: 'Compression flange of the primary superstructure truss',
          },
          matNotAssessed
        )

        // Vertical post
        const vertGeo = new THREE.CylinderGeometry(0.12, 0.12, trussHeight, 8)
        const vertMesh = new THREE.Mesh(vertGeo)
        vertMesh.position.set(x1, 4.8 + trussHeight / 2, z)
        registerMesh(
          vertMesh,
          {
            id: `TRUSS-VERT-${sideName.toUpperCase()}-${i + 1}`,
            name: `${sideName} Vertical Post Member ${i + 1}`,
            type: 'vertical',
            material: 'Structural Steel Tube Section',
            status: 'not_assessed',
            designFunction: 'Transfers shear between top compression and bottom tension chords',
          },
          matNotAssessed
        )

        // Diagonal brace
        const diagLength = Math.hypot(bayWidth, trussHeight)
        const diagAngle = Math.atan2(trussHeight, bayWidth)
        const diagGeo = new THREE.CylinderGeometry(0.1, 0.1, diagLength, 8)
        const diagMesh = new THREE.Mesh(diagGeo)
        diagMesh.position.set(xm, 4.8 + trussHeight / 2, z)
        diagMesh.rotation.z = i % 2 === 0 ? -diagAngle : diagAngle
        registerMesh(
          diagMesh,
          {
            id: `TRUSS-DIAG-${sideName.toUpperCase()}-${i + 1}`,
            name: `${sideName} Diagonal Tie-Brace ${i + 1}`,
            type: 'diagonal',
            material: 'Structural Steel Tie Bar',
            status: 'not_assessed',
            designFunction: 'Carries primary web tension and lateral wind shears',
          },
          matNotAssessed
        )
      }
    })
  }

  return {
    group,
    components,
    modelType: isBrooklyn ? 'Masonry Suspension Arch' : 'Multi-Span Pier & Pratt Truss',
    isIllustrative: true,
  }
}
