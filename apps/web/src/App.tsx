import { Link, useLocation } from "react-router-dom";
import { AppRoutes } from "./routes";

const NAV = [
  { to: "/", label: "总览" },
  { to: "/debug", label: "调试" },
  { to: "/domains", label: "插件" },
  { to: "/config", label: "配置" },
  { to: "/tools", label: "Tools" },
  { to: "/runs", label: "Runs" },
];

export function App() {
  const location = useLocation();

  return (
    <div className="shell">
      <nav className="nav">
        <strong>AI Console</strong>
        {NAV.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            aria-current={location.pathname === item.to ? "page" : undefined}
          >
            {item.label}
          </Link>
        ))}
        <Link to="/contracts">契约</Link>
      </nav>
      <AppRoutes />
    </div>
  );
}
