import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { Loading } from './components/ui'
import { LoginPage } from './pages/LoginPage'

// Pages load on first visit, so the charts library is not in the sign-in bundle.
const AuditPage = lazy(() => import('./pages/admin/AuditPage').then((m) => ({ default: m.AuditPage })))
const ReferencePage = lazy(() => import('./pages/admin/ReferencePage').then((m) => ({ default: m.ReferencePage })))
const UsersPage = lazy(() => import('./pages/admin/UsersPage').then((m) => ({ default: m.UsersPage })))
const CrowdingPage = lazy(() => import('./pages/CrowdingPage').then((m) => ({ default: m.CrowdingPage })))
const DelaysPage = lazy(() => import('./pages/DelaysPage').then((m) => ({ default: m.DelaysPage })))
const DemandPage = lazy(() => import('./pages/DemandPage').then((m) => ({ default: m.DemandPage })))
const ExplorerPage = lazy(() => import('./pages/ExplorerPage').then((m) => ({ default: m.ExplorerPage })))
const MapPage = lazy(() => import('./pages/MapPage').then((m) => ({ default: m.MapPage })))
const ModelsPage = lazy(() => import('./pages/ModelsPage').then((m) => ({ default: m.ModelsPage })))
const OverviewPage = lazy(() => import('./pages/OverviewPage').then((m) => ({ default: m.OverviewPage })))
const PassengersPage = lazy(() => import('./pages/PassengersPage').then((m) => ({ default: m.PassengersPage })))
const PredictionsPage = lazy(() => import('./pages/PredictionsPage').then((m) => ({ default: m.PredictionsPage })))
const RecommendationsPage = lazy(() => import('./pages/RecommendationsPage').then((m) => ({ default: m.RecommendationsPage })))
const RouteDetailPage = lazy(() => import('./pages/RouteDetailPage').then((m) => ({ default: m.RouteDetailPage })))
const RoutesPage = lazy(() => import('./pages/RoutesPage').then((m) => ({ default: m.RoutesPage })))
const StopsPage = lazy(() => import('./pages/StopsPage').then((m) => ({ default: m.StopsPage })))

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <Loading what="session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

/** Route table. Every page except sign-in sits behind RequireAuth inside the Layout shell. */
export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<OverviewPage />} />
            <Route path="map" element={<MapPage />} />
            <Route path="routes" element={<RoutesPage />} />
            <Route path="routes/:routeId" element={<RouteDetailPage />} />
            <Route path="delays" element={<DelaysPage />} />
            <Route path="crowding" element={<CrowdingPage />} />
            <Route path="stops" element={<StopsPage />} />
            <Route path="demand" element={<DemandPage />} />
            <Route path="passengers" element={<PassengersPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="explorer" element={<ExplorerPage />} />
            <Route path="predictions" element={<PredictionsPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="admin/reference" element={<ReferencePage />} />
            <Route path="admin/users" element={<UsersPage />} />
            <Route path="admin/audit" element={<AuditPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
