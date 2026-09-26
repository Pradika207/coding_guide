import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function AdminRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="route-loader" role="status">Preparing the admin workspace…</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
