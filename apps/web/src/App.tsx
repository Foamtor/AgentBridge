import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { AuthProvider, useAuth } from "./features/auth/session";
import { I18nProvider, useI18n } from "./i18n";
import { AppRoutes } from "./routes";

const PRIMARY_NAV = [
  { to: "/admin", key: "admin" },
] as const;

export function App() {
  return <I18nProvider><AuthProvider><AppFrame /></AuthProvider></I18nProvider>;
}

function AppFrame() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session, logout } = useAuth();
  const { t, toggleLocale } = useI18n();
  const authenticated = session?.status === "authenticated";

  useEffect(() => {
    const onAuthError = (event: Event) => {
      const status = (event as CustomEvent<{ status?: number }>).detail?.status;
      if (status === 401) {
        void logout();
        navigate("/login", { replace: true });
      }
      if (status === 403) navigate("/forbidden", { replace: true });
    };
    window.addEventListener("agentbridge:auth-error", onAuthError);
    return () => window.removeEventListener("agentbridge:auth-error", onAuthError);
  }, [logout, navigate]);

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
        {PRIMARY_NAV.map((item) => (
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
