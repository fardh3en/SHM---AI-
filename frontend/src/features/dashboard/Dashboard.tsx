import { useState } from 'react'
import PageHeader from '../../components/layout/PageHeader'
import SectionHeader from '../../components/ui/SectionHeader'
import SystemStatusBar from './SystemStatusBar'
import MetricsStrip from './MetricsStrip'
import RecentInspectionsTable from './RecentInspectionsTable'
import AssetTypeChart from './AssetTypeChart'
import InspectionStatusBar from './InspectionStatusBar'
import QuickActionsPanel from './QuickActionsPanel'
import HeroInspectionAction from './HeroInspectionAction'
import AssetCreateModal from '../assets/AssetCreateModal'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const [isAssetModalOpen, setIsAssetModalOpen] = useState(false)

  return (
    <>
      <SystemStatusBar />

      <PageHeader
        title="Engineering Workspace"
        description="Structural health status, recent inspection activity, and platform overview."
        breadcrumb={[{ label: 'Dashboard' }]}
      />

      <div className={styles.content}>
        {/* ── PRIORITY 1: Prominent Image Inspection Hero ─────────────────── */}
        <section aria-label="Upload crack image" className={styles.section}>
          <HeroInspectionAction onOpenAssetModal={() => setIsAssetModalOpen(true)} />
        </section>

        {/* ── Row 1: Key Metrics ─────────────────────────────────────────── */}
        <section aria-label="Key metrics" className={styles.section}>
          <MetricsStrip />
        </section>

        {/* ── Row 2: Inspections Table + Asset Distribution ─────────────── */}
        <div className={styles.splitRow}>
          {/* Left: recent inspections (60%) */}
          <section className={styles.mainPanel} aria-label="Recent inspections">
            <SectionHeader
              title="Recent Inspections"
              description="Last 10 inspection records across all registered assets."
            />
            <div className={styles.panelSurface}>
              <RecentInspectionsTable />
            </div>
          </section>

          {/* Right: asset type breakdown (40%) */}
          <section className={styles.sidePanel} aria-label="Asset distribution">
            <SectionHeader
              title="Asset Types"
              description="Breakdown of registered structures by category."
            />
            <div className={styles.panelSurface}>
              <AssetTypeChart />
            </div>
          </section>
        </div>

        {/* ── Row 3: Inspection Status + Quick Actions ──────────────────── */}
        <div className={styles.splitRow}>
          {/* Left: status breakdown */}
          <section className={styles.mainPanel} aria-label="Inspection status breakdown">
            <SectionHeader
              title="Inspection Status"
              description="Distribution of all inspection records by processing status."
            />
            <div className={styles.panelSurface}>
              <InspectionStatusBar />
            </div>
          </section>

          {/* Right: quick navigation to future modules */}
          <section className={styles.sidePanel} aria-label="Platform modules">
            <SectionHeader
              title="Platform Modules"
              description="Navigate to analysis and reporting workflows."
            />
            <div className={styles.panelSurface}>
              <QuickActionsPanel />
            </div>
          </section>
        </div>

        {/* ── Capabilities notice ───────────────────────────────────────── */}
        <aside className={styles.notice} role="note">
          <span className={styles.noticeLabel}>SHM-AI Engineering Platform</span>
          <p className={styles.noticeText}>
            Asset Registry, Photo-First Inspection Studio, Autonomous Vision Analysis, and Engineering Reports are active.
            Autonomous Vision Analysis and Decision Engines process telemetry with full audit traceability.
          </p>
        </aside>
      </div>

      {/* Asset Registration Modal */}
      <AssetCreateModal
        isOpen={isAssetModalOpen}
        onClose={() => setIsAssetModalOpen(false)}
      />
    </>
  )
}
