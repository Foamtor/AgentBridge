import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../../i18n";
import { useAuth } from "./session";

export function ChangePasswordPage() {
  const { changePassword } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const strong = next.length >= 8 && /\p{L}/u.test(next) && /\d/.test(next);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    if (!strong || next !== confirm) {
      setError(t("passwordError"));
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      navigate("/");
    } catch (cause) {
      const status = (cause as { status?: number }).status;
      setError(status === 401 ? t("loginError") : t("passwordError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <p className="eyebrow">{t("product")} / {t("admin")}</p>
        <h1>{t("changeTitle")}</h1>
        <p>{t("changeDescription")}</p>
      </section>
      <form className="auth-form" onSubmit={(event) => void submit(event)}>
        <p className="eyebrow">02 / {t("continue")}</p>
        <h2>{t("changeTitle")}</h2>
        <label>{t("currentPassword")}<input name="current-password" autoComplete="current-password" type="password" value={current} onChange={(event) => setCurrent(event.target.value)} /></label>
        <label>{t("newPassword")}<input name="new-password" autoComplete="new-password" type="password" value={next} onChange={(event) => setNext(event.target.value)} /></label>
        <p className={strong ? "password-ok" : "muted"}>{t("passwordHint")}</p>
        <label>{t("confirmPassword")}<input name="confirm-password" autoComplete="new-password" type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label>
        {error ? <p className="error" role="alert">{error}</p> : null}
        <button className="primary" type="submit" disabled={submitting}>{submitting ? "正在保存…" : t("saveEnter")}</button>
      </form>
    </main>
  );
}
