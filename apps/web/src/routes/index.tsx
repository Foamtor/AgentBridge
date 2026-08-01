import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { hasConsoleAdminAccess } from "../features/auth/adminAccess";
import { getToken } from "../features/auth/token";
import { ConfigPage } from "../features/admin/ConfigPage";
import { DomainsPage } from "../features/admin/DomainsPage";
import { ForbiddenPage } from "../features/admin/ForbiddenPage";
import { OverviewPage } from "../features/admin/OverviewPage";
import { KnowledgePage } from "../features/admin/KnowledgePage";
import { PromptsPage } from "../features/admin/PromptsPage";
import { UsagePage } from "../features/admin/UsagePage";
import { RunsPage } from "../features/admin/RunsPage";
import { ToolsPage } from "../features/admin/ToolsPage";
import { AuthCallbackPage } from "../features/auth/callback";
import { ContractsPage } from "../features/contracts/ContractsPage";
import { DebugPage } from "../features/debug/DebugPage";

function AdminRoute({ children }: { children: ReactNode }) {
  if (hasConsoleAdminAccess(getToken())) return children;
  return <Navigate to="/forbidden" replace state={{ message: "当前账号缺少管理权限。" }} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AdminRoute><OverviewPage /></AdminRoute>} />
      <Route path="/debug" element={<DebugPage />} />
      <Route path="/domains" element={<AdminRoute><DomainsPage /></AdminRoute>} />
      <Route path="/config" element={<AdminRoute><ConfigPage /></AdminRoute>} />
      <Route path="/tools" element={<AdminRoute><ToolsPage /></AdminRoute>} />
      <Route path="/runs" element={<AdminRoute><RunsPage /></AdminRoute>} />
      <Route path="/prompts" element={<AdminRoute><PromptsPage /></AdminRoute>} />
      <Route path="/usage" element={<AdminRoute><UsagePage /></AdminRoute>} />
      <Route path="/knowledge" element={<AdminRoute><KnowledgePage /></AdminRoute>} />
      <Route path="/forbidden" element={<ForbiddenPage />} />
      <Route path="/contracts" element={<ContractsPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
