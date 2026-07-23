import { Navigate, Route, Routes } from "react-router-dom";
import { AuthCallbackPage } from "../features/auth/callback";
import { ContractsPage } from "../features/contracts/ContractsPage";
import { DebugPage } from "../features/debug/DebugPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<DebugPage />} />
      <Route path="/contracts" element={<ContractsPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
