import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { LoginPage } from "../features/auth/LoginPage";
import { ChangePasswordPage } from "../features/auth/ChangePasswordPage";
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
import { VerificationWorkbench } from "../features/verification/VerificationWorkbench";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup-password" element={<ProtectedRoute passwordChangeOnly />}><Route index element={<ChangePasswordPage />} /></Route>
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<VerificationWorkbench />} />
        <Route path="/debug" element={<Navigate to="/?mode=advanced" replace />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/admin" element={<OverviewPage />} />
        <Route path="/domains" element={<DomainsPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/prompts" element={<PromptsPage />} />
        <Route path="/usage" element={<UsagePage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
      </Route>
      <Route path="/forbidden" element={<ForbiddenPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
