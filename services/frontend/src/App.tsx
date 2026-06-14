import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Projects from './pages/Projects'
import Project from './pages/Project'
import DataSources from './pages/DataSources'
import SampleBrowser from './pages/SampleBrowser'
import Datasets from './pages/Datasets'
import DatasetView from './pages/DatasetView'
import CommitDetail from './pages/CommitDetail'
import Workflows from './pages/Workflows'
import WorkflowBuilder from './pages/WorkflowBuilder'
import RunView from './pages/RunView'
import Models from './pages/Models'
import ModelDetail from './pages/ModelDetail'
import ProjectSettings from './pages/ProjectSettings'
import Login from './pages/Login'
import Register from './pages/Register'
import { isAuthenticated } from './api/auth'

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects"                              element={<Projects />} />
        <Route path="/projects/:id"                          element={<Project />} />
        <Route path="/projects/:id/data-sources"             element={<DataSources />} />
        <Route path="/projects/:id/samples"                  element={<SampleBrowser />} />
        <Route path="/projects/:id/datasets"                 element={<Datasets />} />
        <Route path="/datasets/:id"                          element={<DatasetView />} />
        <Route path="/datasets/:id/commits/:cid"             element={<CommitDetail />} />
        <Route path="/projects/:id/workflows"                element={<Workflows />} />
        <Route path="/workflows/:id"                         element={<WorkflowBuilder />} />
        <Route path="/runs/:id"                              element={<RunView />} />
        <Route path="/projects/:id/models"                   element={<Models />} />
        <Route path="/models/:id"                            element={<ModelDetail />} />
        <Route path="/projects/:id/settings"                 element={<ProjectSettings />} />
      </Route>
    </Routes>
  )
}
