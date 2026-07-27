import { Navigate, Route, Routes } from "react-router-dom";
import { ConfigPage } from "../features/admin/ConfigPage";
import { DomainsPage } from "../features/admin/DomainsPage";
import { ForbiddenPage } from "../features/admin/ForbiddenPage";
import { OverviewPage } from "../features/admin/OverviewPage";
import { AuthCallbackPage } from "../features/auth/callback";
import { ContractsPage } from "../features/contracts/ContractsPage";
import { DebugPage } from "../features/debug/DebugPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/debug" element={<DebugPage />} />
      <Route path="/domains" element={<DomainsPage />} />
      <Route path="/config" element={<ConfigPage />} />
      <Route path="/forbidden" element={<ForbiddenPage />} />
      <Route path="/contracts" element={<ContractsPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
