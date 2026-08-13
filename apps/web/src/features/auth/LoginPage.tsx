import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./session";
import { useI18n } from "../../i18n";

export function LoginPage() {
  const { login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const session = await login("admin", password);
      navigate(session.status === "password_change_required" ? "/setup-password" : "/");
    } catch (cause) {
      const failure = cause as { message?: string; status?: number };
      if (failure.status === 429) setError(t("loginRateLimited"));
      else if (failure.message === "cross_site_request") setError(t("loginOriginError"));
      else if (failure.status === 401) setError(t("loginError"));
      else setError(t("loginUnavailable"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <p className="eyebrow">{t("product")} / {t("preview")}</p>
        <h1>{t("loginIntro")}</h1>
        <p>{t("loginDescription")}</p>
      </section>
      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <p className="eyebrow">01 / {t("admin")}</p>
        <h2>{t("loginTitle")}</h2>
        <label>{t("username")}<input name="username" autoComplete="username" value="admin" readOnly /></label>
        <label>{t("password")}<input name="password" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus /></label>
        {error ? <p className="error" role="alert">{error}</p> : null}
        <button className="primary" type="submit" disabled={submitting || !password}>{submitting ? "正在登录…" : t("continue")}</button>
        <p className="muted">{t("loginHelp")}</p>
      </form>
    </main>
  );
}
