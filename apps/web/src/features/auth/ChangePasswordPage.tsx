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
  const strong = next.length >= 12 && !/admin/i.test(next) && !/password|123456|qwerty/i.test(next);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!strong || next !== confirm) {
      setError(t("passwordError"));
      return;
    }
    try {
      await changePassword(current, next);
      navigate("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
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
        <label>{t("currentPassword")}<input type="password" value={current} onChange={(event) => setCurrent(event.target.value)} /></label>
        <label>{t("newPassword")}<input type="password" value={next} onChange={(event) => setNext(event.target.value)} /></label>
        <p className={strong ? "password-ok" : "muted"}>{t("passwordHint")}</p>
        <label>{t("confirmPassword")}<input type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label>
        {error ? <p className="error">{error}</p> : null}
        <button className="primary" type="submit">{t("saveEnter")}</button>
      </form>
    </main>
  );
}
