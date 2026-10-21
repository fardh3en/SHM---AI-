import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildTunnelModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  const latestInspection = inspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(latestInspection)

  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A',
    roughness: 0.35,
    metalness: 0.4,
  })
  const matNominal = new THREE.MeshStandardMaterial({
    color: '#B6BDA8',
    roughness: 0.5,
    metalness: 0.3,
  })
  const matLining = new THREE.MeshStandardMaterial({
    color: '#3F4448',
    roughness: 0.65,
    metalness: 0.35,
  })
  const matRoadway = new THREE.MeshStandardMaterial({
    color: '#2A2C2E',
    roughness: 0.8,
    metalness: 0.1,
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

  // ── Tunnel Segmental Rings ────────────────────────────────────────────────
  const numRings = 12
  const ringLength = 2.2
  const outerRadius = 4.8
  const innerRadius = 4.3

  for (let r = 0; r < numRings; r++) {
    const ringZ = (r - numRings / 2) * ringLength
    const ringNumber = 38 + r

    // Each ring is divided into quadrants / segment panels
    const segmentsPerRing = 4
    for (let s = 0; s < segmentsPerRing; s++) {
      const angleStart = (s * Math.PI) / 2
      const angleLength = Math.PI / 2 - 0.05 // Tiny gap representing bolted flange joint

      // Segment geometry: extruded arc section
      const shape = new THREE.Shape()
      const segmentsArc = 16

      // Outer arc
      for (let i = 0; i <= segmentsArc; i++) {
        const theta = angleStart + (i / segmentsArc) * angleLength
        const x = outerRadius * Math.cos(theta)
        const y = outerRadius * Math.sin(theta)
        if (i === 0) shape.moveTo(x, y)
        else shape.lineTo(x, y)
      }
      // Inner arc (reverse)
      for (let i = segmentsArc; i >= 0; i--) {
        const theta = angleStart + (i / segmentsArc) * angleLength
        const x = innerRadius * Math.cos(theta)
        const y = innerRadius * Math.sin(theta)
        shape.lineTo(x, y)
      }
      shape.closePath()

      const extrudeSettings = {
        depth: ringLength - 0.08,
        bevelEnabled: false,
      }
      const segGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings)
      const segMesh = new THREE.Mesh(segGeo)
      segMesh.position.set(0, 0, ringZ)

      const isPanel42 = ringNumber === 42 && s === 1
      const isNominalPanel = ringNumber === 41 || ringNumber === 43

      const segStatus = isPanel42 && hasFindings
        ? 'assessed_findings'
        : isNominalPanel
        ? 'assessed_nominal'
        : 'not_assessed'

      const segMat = segStatus === 'assessed_findings'
        ? matFindings
        : segStatus === 'assessed_nominal'
        ? matNominal
        : matLining

      registerMesh(
        segMesh,
        {
          id: `TUNNEL-SEG-R${ringNumber}-S${s + 1}`,
          name: isPanel42 ? 'Segment Panel 42 (Upper Crown Joint)' : `Ring ${ringNumber} Segment ${s + 1}`,
          type: 'lining_segment',
          material: asset.material || 'Cast-Iron Bolted Segment with Concrete Infills',
          status: segStatus,
          designFunction: 'Carries circumferential hoop compression and earth/hydrostatic loads',
          dimensions: `Ring Length: 2.2m · Outer Radius: 4.8m · Sector: ${s * 90}°-${(s + 1) * 90}°`,
          defectSummary: isPanel42 && hasFindings
            ? `Active inspection findings: ${latestInspection?.notes || 'Transverse crack on segment panel 42. Minor spalling near joint.'}`
            : undefined,
          findingsCount: isPanel42 ? latestInspection?.defect_count : 0,
          linkedEvidencePaths: isPanel42
            ? ['/uploads/evidence/lincoln_tunnel_south_tube_interior.jpg', '/uploads/evidence/lincoln_tunnel_lining_segments_1936.jpg']
            : undefined,
        },
        segMat
      )
    }
  }

  // ── Roadway Invert Deck Slab ─────────────────────────────────────────────
  const roadW = innerRadius * 1.55
  const roadL = numRings * ringLength
  const roadGeo = new THREE.BoxGeometry(roadW, 0.4, roadL)
  const roadMesh = new THREE.Mesh(roadGeo)
  roadMesh.position.set(0, -innerRadius + 1.2, 0)
  registerMesh(
    roadMesh,
    {
      id: 'TUNNEL-ROADWAY-DECK',
      name: 'Lower Invert Roadway Slab',
      type: 'deck',
      material: 'Reinforced concrete roadway invert slab on drainage bed',
      status: 'not_assessed',
      designFunction: 'Supports vehicular traffic lanes and accommodates below-deck service utilities',
      dimensions: `${roadW.toFixed(1)}m wide × ${roadL.toFixed(1)}m long × 0.4m thick`,
    },
    matRoadway
  )

  // ── Overhead Exhaust Ventilation Ceiling Duct ────────────────────────────
  const ventW = innerRadius * 1.4
  const ventGeo = new THREE.BoxGeometry(ventW, 0.2, roadL)
  const ventMesh = new THREE.Mesh(ventGeo)
  ventMesh.position.set(0, innerRadius - 1.2, 0)
  registerMesh(
    ventMesh,
    {
      id: 'TUNNEL-VENT-CEILING',
      name: 'Transverse Ventilation False Ceiling',
      type: 'ceiling_duct',
      material: 'Suspended precast concrete panels with stainless steel hangers',
      status: 'not_assessed',
      designFunction: 'Separates vehicle tunnel tube from upper exhaust air plenum',
      dimensions: `${ventW.toFixed(1)}m × 0.2m × ${roadL.toFixed(1)}m`,
    },
    matLining
  )

  return {
    group,
    components,
    modelType: 'Bored Shield Segmental Ring Tunnel',
    isIllustrative: true,
  }
}
