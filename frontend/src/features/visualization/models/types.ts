/**
 * 3D Structural Visualization Domain Types
 */

export type ComponentStatus =
  | 'assessed_findings'     // Inspected with active defects / findings reported
  | 'assessed_nominal'      // Inspected with no active anomalies reported
  | 'not_assessed'          // No inspection data recorded for this member
  | 'illustrative'          // Illustrative geometric reference member

export type StructuralMemberType =
  | 'pier'
  | 'deck'
  | 'girder'
  | 'chord_top'
  | 'chord_bottom'
  | 'diagonal'
  | 'vertical'
  | 'arch_voussoir'
  | 'keystone'
  | 'bearing'
  | 'lining_segment'
  | 'ceiling_duct'
  | 'slab_bay'
  | 'column'
  | 'drop_panel'
  | 'pipe_carrier'
  | 'insulation_jacket'
  | 'valve_manifold'
  | 'sluice_wall'
  | 'inlet_arch'
  | 'abutment'
  | 'parapet'
  | 'crosshead'
  | 'retaining_wall'
  | 'weir_crest'
  | 'sluice_gate'
  | 'culvert_portal'
  | 'embankment'
  | 'intake_screen'

export interface StructuralComponentData {
  id: string
  name: string
  type: StructuralMemberType
  material: string
  status: ComponentStatus
  designFunction: string
  dimensions?: string
  defectSummary?: string
  findingsCount?: number
  linkedEvidencePaths?: string[]
  inspectionNotes?: string
}

export interface ModelBuildResult {
  group: import('three').Group
  components: Map<string, StructuralComponentData>
  modelType: string
  isIllustrative: boolean
}
