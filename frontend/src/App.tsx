import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './features/home/HomePage'
import Dashboard from './features/dashboard/Dashboard'
import AssetListPage from './features/assets/AssetListPage'
import AssetDetailPage from './features/assets/AssetDetailPage'
import InspectionStudioPage from './features/inspections/InspectionStudioPage'
import StructuralHealthPage from './features/visualization/StructuralHealthPage'
import VisionAnalysisPage from './features/vision/VisionAnalysisPage'
import ReportsPage from './features/reports/ReportsPage'
import AppShell from './components/layout/AppShell'

export default function App() {
  return (
    <Routes>
      {/* Public homepage — no app shell */}
      <Route path="/" element={<HomePage />} />

      {/* Application routes — wrapped in shared shell */}
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/assets" element={<AssetListPage />} />
        <Route path="/assets/:id" element={<AssetDetailPage />} />
        <Route path="/inspections" element={<InspectionStudioPage />} />
        <Route path="/structural-health" element={<StructuralHealthPage />} />
        <Route path="/vision" element={<VisionAnalysisPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

