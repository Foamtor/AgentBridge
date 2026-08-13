import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { adminFetch } from "./adminFetch";

type ConfigItem = {
  key: string;
  value: unknown;
  tier: string;
  description: string;
  configured?: boolean;
  writable?: boolean;
  source?: "database" | "memory" | "deployment";
};

const copy = {
  "zh-CN": {
    title: "平台配置",
    intro: "在线调整仅适用于无需重启的运行参数，保存后立即生效并持久化到数据库。部署、连接和安全配置仍由环境变量或部署系统管理。",
    runtime: "在线运行参数",
    runtimeHint: "每次保存都会在服务端确认当前管理员密码，并记录配置变更。",
    password: "确认当前密码",
    passwordHint: "每次保存都需要重新验证；密码不会被保存。",
    key: "键",
    value: "当前值",
    source: "来源",
    description: "作用",
    save: "保存",
    saving: "保存中...",
    database: "数据库覆盖",
    memory: "本地临时值",
    deployment: "部署默认值",
    saved: "已保存，配置已生效。",
    readOnly: "部署与安全配置",
    readOnlyHint: "这些参数会影响服务组装、基础设施或密钥边界，不能在运行中的控制台修改。密钥只显示是否已配置。",
    tier: "类型",
    configured: "已配置",
    notConfigured: "未配置",
    loading: "正在读取配置...",
    invalidNumber: "请输入 0 到 100000 的整数。",
    error: "无法保存配置，请确认当前密码和服务状态。",
    authError: "当前密码不正确或会话已失效。",
  },
  en: {
    title: "Platform configuration",
    intro: "Only restart-free runtime parameters can be changed here. They take effect immediately and are persisted in the database. Deployment, connection, and security settings remain deployment-managed.",
    runtime: "Live runtime parameters",
    runtimeHint: "Every save verifies the current administrator password on the server and records the change.",
    password: "Confirm current password",
    passwordHint: "The password is verified on every save and is never stored.",
    key: "Key",
    value: "Current value",
    source: "Source",
    description: "Effect",
    save: "Save",
    saving: "Saving...",
    database: "Database override",
    memory: "Local temporary value",
    deployment: "Deployment default",
    saved: "Saved and active.",
    readOnly: "Deployment and security settings",
    readOnlyHint: "These settings affect service composition, infrastructure, or secrets and cannot be changed in a running console. Secrets only show whether they are configured.",
    tier: "Type",
    configured: "Configured",
    notConfigured: "Not configured",
    loading: "Loading configuration...",
    invalidNumber: "Enter an integer from 0 to 100000.",
    error: "Could not save the configuration. Check the current password and service status.",
    authError: "The current password is incorrect or the session has expired.",
  },
} as const;

export function ConfigPage() {
  const { locale } = useI18n();
  const text = copy[locale];
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string | boolean>>({});
  const [currentPassword, setCurrentPassword] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void adminFetch<{ items: ConfigItem[] }>("/admin/config")
      .then((body) => {
        setItems(body.items);
        setDrafts(Object.fromEntries(body.items.filter((item) => item.writable).map((item) => [item.key, typeof item.value === "boolean" ? item.value : String(item.value ?? "")])))
      })
      .catch(() => setError(text.error));
  }, [text.error]);

  const editable = items.filter((item) => item.writable);
  const readOnly = items.filter((item) => !item.writable);

  async function save(item: ConfigItem) {
    setError(null);
    setNotice(null);
    const draft = drafts[item.key];
    const numericValue = Number(draft);
    const value: number | boolean = typeof item.value === "boolean" ? draft === true : numericValue;
    if (typeof item.value !== "boolean" && (!Number.isInteger(numericValue) || numericValue < 0 || numericValue > 100000)) {
      setError(text.invalidNumber);
      return;
    }
    setSaving(item.key);
    try {
      const saved = await adminFetch<ConfigItem>(`/admin/config/${encodeURIComponent(item.key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value, current_password: currentPassword }),
      });
      setItems((current) => current.map((existing) => existing.key === item.key ? { ...existing, value: saved.value, source: saved.source } : existing));
      setCurrentPassword("");
      setNotice(text.saved);
    } catch (err) {
      setError((err as { status?: number }).status === 401 ? text.authError : text.error);
    } finally {
      setSaving(null);
    }
  }

  return (
    <main className="page config-page">
      <header className="config-header">
        <h1>{text.title}</h1>
        <p className="lede">{text.intro}</p>
      </header>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {notice ? <p className="config-notice" role="status">{notice}</p> : null}
      {!items.length && !error ? <p className="muted">{text.loading}</p> : null}

      {editable.length ? <section className="config-section" aria-labelledby="runtime-config-title">
        <div className="config-section-heading">
          <div><h2 id="runtime-config-title">{text.runtime}</h2><p>{text.runtimeHint}</p></div>
          <label className="config-password"><span>{text.password}</span><input aria-label={text.password} type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" /><small>{text.passwordHint}</small></label>
        </div>
        <table className="config-table config-edit-table">
          <thead><tr><th>{text.key}</th><th>{text.value}</th><th>{text.source}</th><th>{text.description}</th><th><span className="sr-only">{text.save}</span></th></tr></thead>
          <tbody>{editable.map((item) => <tr key={item.key}>
            <td><code>{item.key}</code></td>
            <td>{typeof item.value === "boolean" ? <label className="toggle-field"><input aria-label={item.key} type="checkbox" checked={drafts[item.key] === true} onChange={(event) => setDrafts((current) => ({ ...current, [item.key]: event.target.checked }))} /><span>{drafts[item.key] ? "true" : "false"}</span></label> : <input aria-label={item.key} className="config-number" type="number" min="0" max="100000" step="1" value={String(drafts[item.key] ?? "")} onChange={(event) => setDrafts((current) => ({ ...current, [item.key]: event.target.value }))} />}</td>
            <td><span className="config-source">{item.source === "database" ? text.database : item.source === "memory" ? text.memory : text.deployment}</span></td>
            <td className="muted">{item.description}</td>
            <td><button type="button" className="config-save" disabled={saving !== null} onClick={() => void save(item)}>{saving === item.key ? text.saving : text.save}</button></td>
          </tr>)}</tbody>
        </table>
      </section> : null}

      {readOnly.length ? <section className="config-section" aria-labelledby="readonly-config-title">
        <div className="config-section-heading"><div><h2 id="readonly-config-title">{text.readOnly}</h2><p>{text.readOnlyHint}</p></div></div>
        <table className="config-table">
          <thead><tr><th>{text.key}</th><th>{text.tier}</th><th>{text.value}</th><th>{text.description}</th></tr></thead>
          <tbody>{readOnly.map((item) => <tr key={item.key}><td><code>{item.key}</code></td><td>{item.tier}</td><td>{item.tier === "C" ? item.configured ? text.configured : text.notConfigured : String(item.value ?? "-")}</td><td className="muted">{item.description}</td></tr>)}</tbody>
        </table>
      </section> : null}
    </main>
  );
}
