import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData, ComponentStatus } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildBuildingModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  const completedInspections = inspections.filter((i) => i.status === 'completed')
  const latestCompleted = completedInspections[0]
  const inspectionWithFindings = completedInspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(inspectionWithFindings)

  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A',
    roughness: 0.35,
    metalness: 0.3,
  })
  const matNominal = new THREE.MeshStandardMaterial({
    color: '#B6BDA8',
    roughness: 0.45,
    metalness: 0.2,
  })
  const matConcrete = new THREE.MeshStandardMaterial({
    color: '#525048',
    roughness: 0.7,
    metalness: 0.1,
  })
  const matSteel = new THREE.MeshStandardMaterial({
    color: '#3A3C40',
    roughness: 0.5,
    metalness: 0.6,
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

  // Multi-story post-tensioned garage bays (3 × 2 grid, 2 levels)
  const colsX = [-8, 0, 8]
  const colsZ = [-6, 6]
  const levels = [0, 5]

  // Columns & drop panels
  colsX.forEach((x, ix) => {
    colsZ.forEach((z, iz) => {
      // Column shaft
      const colGeo = new THREE.BoxGeometry(0.9, 6.5, 0.9)
      const colMesh = new THREE.Mesh(colGeo)
      colMesh.position.set(x, 2.5, z)
      registerMesh(
        colMesh,
        {
          id: `COL-GRID-${ix + 1}-${iz + 1}`,
          name: `Reinforced Concrete Column (Grid ${String.fromCharCode(65 + ix)}-${iz + 1})`,
          type: 'column',
          material: 'Reinforced Concrete (Grade C50)',
          status: 'not_assessed',
          designFunction: 'Carries cumulative gravity loads and lateral moment frames',
          dimensions: '0.9m × 0.9m square section × 6.5m height',
        },
        matConcrete
      )

      // Column drop panel capital at ceiling
      const dropGeo = new THREE.BoxGeometry(2.4, 0.45, 2.4)
      const dropMesh = new THREE.Mesh(dropGeo)
      dropMesh.position.set(x, 5.0, z)
      registerMesh(
        dropMesh,
        {
          id: `DROP-PANEL-${ix + 1}-${iz + 1}`,
          name: `Column Capital Drop Panel (${String.fromCharCode(65 + ix)}-${iz + 1})`,
          type: 'drop_panel',
          material: 'Heavily reinforced shear head collar',
          status: 'not_assessed',
          designFunction: 'Prevents punching shear failure at slab-column connection',
          dimensions: '2.4m × 2.4m × 0.45m',
        },
        matSteel
      )
    })
  })

  // Post-tensioned deck slab spans
  // Bay C-2 has the severe carbonation and rebar exposure finding
  levels.forEach((lvlY, lvlIdx) => {
    const isLevelC = lvlIdx === 1 // Upper deck level C

    for (let bx = 0; bx < colsX.length - 1; bx++) {
      const xMid = (colsX[bx] + colsX[bx + 1]) / 2
      const spanW = Math.abs(colsX[bx + 1] - colsX[bx]) - 0.2
      const spanD = Math.abs(colsZ[1] - colsZ[0])

      const isDefectBay = isLevelC && bx === 0
      let bayStatus: ComponentStatus = 'not_assessed'
      if (isDefectBay) {
        if (hasFindings && inspectionWithFindings) {
          bayStatus = 'assessed_findings'
        } else if (completedInspections.length > 0) {
          bayStatus = 'assessed_nominal'
        }
      }

      const bayMat = bayStatus === 'assessed_findings'
        ? matFindings
        : bayStatus === 'assessed_nominal'
        ? matNominal
        : matConcrete

      const slabGeo = new THREE.BoxGeometry(spanW, 0.4, spanD)
      const slabMesh = new THREE.Mesh(slabGeo)
      slabMesh.position.set(xMid, lvlY + 5.2, 0)

      registerMesh(
        slabMesh,
        {
          id: `SLAB-BAY-LVL${lvlIdx + 1}-BAY${bx + 1}`,
          name: isDefectBay ? 'Deck C - Span Bay 1-2' : `Parking Deck Slab Bay ${bx + 1} (Level ${lvlIdx + 1})`,
          type: 'slab_bay',
          material: asset.material || 'Post-Tensioned Concrete (Unbonded Monostrand)',
          status: bayStatus,
          designFunction: 'Two-way post-tensioned slab resisting vehicle wheel loads',
          dimensions: `${spanW.toFixed(1)}m × ${spanD.toFixed(1)}m × 0.4m`,
          defectSummary: bayStatus === 'assessed_findings' && inspectionWithFindings
            ? `${inspectionWithFindings.defect_count} structural defect(s) detected during inspection. Notes: ${inspectionWithFindings.notes || 'Anomalies identified.'}`
            : undefined,
          findingsCount: bayStatus === 'assessed_findings' ? inspectionWithFindings?.defect_count : 0,
          inspectionId: bayStatus === 'assessed_findings' ? inspectionWithFindings?.id : bayStatus === 'assessed_nominal' ? latestCompleted?.id : undefined,
          inspectionDate: bayStatus === 'assessed_findings' ? inspectionWithFindings?.created_at : bayStatus === 'assessed_nominal' ? latestCompleted?.created_at : undefined,
          linkedEvidencePaths: bayStatus === 'assessed_findings' && inspectionWithFindings?.input_path
            ? [inspectionWithFindings.input_path]
            : undefined,
        },
        bayMat
      )
    }
  })

  return {
    group,
    components,
    modelType: 'Multi-Bay Post-Tensioned Parking Deck Frame',
    isIllustrative: true,
  }
}
