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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const session = await login("admin", password);
      navigate(session.status === "password_change_required" ? "/setup-password" : "/");
    } catch (cause) {
      setError((cause as { status?: number }).status === 429 ? t("loginRateLimited") : t("loginError"));
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
        <label>{t("username")}<input value="admin" readOnly /></label>
        <label>{t("initialPassword")}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus /></label>
        {error ? <p className="error">{error}</p> : null}
        <button className="primary" type="submit">{t("continue")}</button>
        <p className="muted">{t("loginHelp")}</p>
      </form>
    </main>
  );
}
