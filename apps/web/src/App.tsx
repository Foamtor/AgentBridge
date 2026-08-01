import { Link, useLocation } from "react-router-dom";
import { hasConsoleAdminAccess } from "./features/auth/adminAccess";
import { getToken } from "./features/auth/token";
import { AppRoutes } from "./routes";

const ADMIN_NAV = [
  { to: "/", label: "总览" },
  { to: "/domains", label: "插件" },
  { to: "/config", label: "配置" },
  { to: "/tools", label: "Tools" },
  { to: "/runs", label: "Runs" },
  { to: "/prompts", label: "Prompts" },
  { to: "/usage", label: "用量" },
  { to: "/knowledge", label: "知识" },
];

export function App() {
  const location = useLocation();
  const canUseAdmin = hasConsoleAdminAccess(getToken());

  return (
    <div className="shell">
      <nav className="nav">
        <strong>AI Console</strong>
        <Link to="/debug" aria-current={location.pathname === "/debug" ? "page" : undefined}>
          调试
        </Link>
        {canUseAdmin
          ? ADMIN_NAV.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            aria-current={location.pathname === item.to ? "page" : undefined}
          >
            {item.label}
          </Link>
            ))
          : null}
        <Link to="/contracts">契约</Link>
      </nav>
      <AppRoutes />
    </div>
  );
}
