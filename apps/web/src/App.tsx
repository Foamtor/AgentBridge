import { Link, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./features/auth/session";
import { I18nProvider, useI18n } from "./i18n";
import { AppRoutes } from "./routes";

const ADMIN_NAV = [
  { to: "/admin", key: "admin" },
  { to: "/domains", key: "plugins" },
  { to: "/config", key: "config" },
  { to: "/models", key: "models" },
  { to: "/tools", key: "tools" },
  { to: "/runs", key: "runs" },
  { to: "/prompts", key: "prompts" },
  { to: "/usage", key: "usage" },
  { to: "/knowledge", key: "knowledge" },
] as const;

export function App() {
  return <I18nProvider><AuthProvider><AppFrame /></AuthProvider></I18nProvider>;
}

function AppFrame() {
  const location = useLocation();
  const { session, logout } = useAuth();
  const { t, toggleLocale } = useI18n();
  const authenticated = session?.status === "authenticated";

  if (!authenticated) return <AppRoutes />;

  return (
    <div className="shell">
      <nav className="nav">
        <strong>{t("product")}</strong>
        <Link to="/" aria-current={location.pathname === "/" ? "page" : undefined}>
          {t("verify")}
        </Link>
        <Link to="/playground" aria-current={location.pathname === "/playground" ? "page" : undefined}>
          {t("playground")}
        </Link>
        {ADMIN_NAV.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            aria-current={location.pathname === item.to ? "page" : undefined}
          >
            {t(item.key)}
          </Link>
        ))}
        <Link to="/contracts">{t("contracts")}</Link>
        <span className="nav-spacer" />
        <button className="nav-button" type="button" onClick={toggleLocale}>{t("language")}</button>
        <button className="nav-button" type="button" onClick={() => void logout()}>{t("logout")}</button>
      </nav>
      <AppRoutes />
    </div>
  );
}
