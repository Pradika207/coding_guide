import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import AdminRoute from './components/AdminRoute';
import ProtectedRoute from './components/ProtectedRoute';
import AdminDashboard from './pages/Admin';
import Assessment from './pages/Assessment';
import Dashboard from './pages/Dashboard';
import Learn from './pages/Learn';
import Lesson from './pages/Lesson';
import Login from './pages/Login';
import Practice from './pages/Practice';

function AppRoutes() {
  return <Routes>
    <Route path="/login" element={<Login />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/assessment" element={<Assessment />} />
      <Route path="/learn" element={<Learn />} />
      <Route path="/learn/lesson/:lessonId" element={<Lesson />} />
      <Route path="/practice" element={<Practice />} />
      <Route path="/practice/:questionId" element={<Practice />} />
      <Route element={<AdminRoute />}>
        <Route path="/admin" element={<AdminDashboard />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Route>
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes>;
}

export default function App() {
  return <AuthProvider><AppRoutes /></AuthProvider>;
}
