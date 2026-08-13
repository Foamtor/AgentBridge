import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../../i18n";

export function ForbiddenPage() {
  const { locale } = useI18n();
  const location = useLocation();
  const message =
    (location.state as { message?: string } | null)?.message ??
    locale === "en" ? "Your account does not have permission to open this page." : "当前账号没有访问此页面的权限。";
  const copy = locale === "en" ? { title: "Access denied", back: "Back to verification" } : { title: "无权限", back: "返回验证工作台" };

  return (
    <main className="page">
      <h1>{copy.title}</h1>
      <p className="error">{message}</p>
      <p>
        <Link to="/">{copy.back}</Link>
      </p>
    </main>
  );
}
