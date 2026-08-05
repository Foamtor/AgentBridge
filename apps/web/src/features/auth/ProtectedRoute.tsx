import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./session";

export function ProtectedRoute({ passwordChangeOnly = false }: { passwordChangeOnly?: boolean }) {
  const { session } = useAuth();
  if (!session) return <main className="page muted">正在检查会话…</main>;
  if (session.status === "anonymous") return <Navigate to="/login" replace />;
  if (passwordChangeOnly) return session.status === "password_change_required" ? <Outlet /> : <Navigate to="/" replace />;
  if (session.status === "password_change_required") return <Navigate to="/setup-password" replace />;
  return <Outlet />;
}
