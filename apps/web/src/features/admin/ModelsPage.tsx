import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { adminFetch } from "./adminFetch";

type Model = {
  alias: string;
  api_base: string;
  model_name: string;
  temperature: number;
  enabled: boolean;
  key_configured: boolean;
  runtime_ready: boolean;
  updated_at?: string;
};

type Form = {
  alias: string;
  api_base: string;
  model_name: string;
  api_key: string;
  temperature: string;
  enabled: boolean;
};

const emptyForm = (): Form => ({
  alias: "",
  api_base: "https://api.openai.com/v1",
  model_name: "",
  api_key: "",
  temperature: "0",
  enabled: true,
});

export function ModelsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? {
    title: "Model management", intro: "Configure OpenAI-compatible models. API keys are submitted only when saved, encrypted in PostgreSQL, and never returned to the console.", missing: "MODEL_CONFIG_ENCRYPTION_KEY is not set; model credentials cannot be saved.", add: "Add model", edit: "Edit", alias: "Alias", base: "API base", model: "Model name", key: "API key", replaceKey: "Replace API key (blank keeps it)", temperature: "Temperature", enabled: "Enable for the verification workbench", save: "Save changes", cancel: "Cancel", configured: "Configured models", empty: "No models configured. Fake demo remains available in the verification workbench.", available: "Available", unavailable: "Credential unavailable", disabled: "Disabled", keyConfigured: "key configured", saved: "Model saved. The key will not be shown again.", updated: "Model updated.", remove: "Delete", confirm: "Delete model alias", date: "Updated",
  } : {
    title: "模型管理", intro: "配置 OpenAI 兼容模型。API Key 仅在保存时提交，数据库只保存加密密文，控制台不会返回明文。", missing: "未设置 MODEL_CONFIG_ENCRYPTION_KEY，不能保存模型凭据。", add: "添加模型", edit: "编辑", alias: "别名", base: "API 地址", model: "模型名称", key: "API Key", replaceKey: "替换 API Key（留空则保留）", temperature: "温度", enabled: "启用并用于验证工作台", save: "保存变更", cancel: "取消", configured: "已配置模型", empty: "尚未配置模型。Fake 演示仍可在验证工作台中运行。", available: "可用", unavailable: "凭据不可用", disabled: "已停用", keyConfigured: "密钥已配置", saved: "模型配置已保存。密钥不会再次显示。", updated: "模型配置已更新。", remove: "删除", confirm: "删除模型别名", date: "更新时间",
  };
  const [models, setModels] = useState<Model[]>([]);
  const [encryptionReady, setEncryptionReady] = useState(false);
  const [form, setForm] = useState<Form>(emptyForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const patch = (next: Partial<Form>) => setForm((current) => ({ ...current, ...next }));

  const load = async () => {
    try {
      const body = await adminFetch<{ models: Model[]; encryption_ready: boolean }>("/admin/models");
      setModels(body.models);
      setEncryptionReady(body.encryption_ready);
      setError(null);
    } catch (reason) {
      setError(String(reason));
    }
  };

  useEffect(() => { void load(); }, []);

  async function submit() {
    setMessage(null);
    setError(null);
    const payload = {
      api_base: form.api_base,
      model_name: form.model_name,
      api_key: form.api_key || undefined,
      temperature: Number(form.temperature),
      enabled: form.enabled,
    };
    try {
      if (editing) {
        await adminFetch(`/admin/models/${encodeURIComponent(editing)}`, {
          method: "PUT", body: JSON.stringify(payload),
        });
      } else {
        await adminFetch("/admin/models", {
          method: "POST",
          body: JSON.stringify({ ...payload, alias: form.alias, api_key: form.api_key }),
        });
      }
      setMessage(editing ? copy.updated : copy.saved);
      setEditing(null);
      setForm(emptyForm());
      await load();
    } catch (reason) {
      setError(String(reason));
    }
  }

  function startEdit(model: Model) {
    setEditing(model.alias);
    setForm({
      alias: model.alias,
      api_base: model.api_base,
      model_name: model.model_name,
      api_key: "",
      temperature: String(model.temperature),
      enabled: model.enabled,
    });
    setMessage(null);
  }

  async function remove(alias: string) {
    if (!window.confirm(`${copy.confirm} ${alias}?`)) return;
    try {
      await adminFetch(`/admin/models/${encodeURIComponent(alias)}`, { method: "DELETE" });
      await load();
    } catch (reason) {
      setError(String(reason));
    }
  }

  return <main className="page models-page">
    <header><h1>{copy.title}</h1><p className="lede">{copy.intro}</p></header>
    {!encryptionReady ? <p className="error">{copy.missing}</p> : null}
    {error ? <p className="error">{error}</p> : null}
    {message ? <p className="password-ok">{message}</p> : null}
    <section className="model-editor" aria-label="模型配置">
      <h2>{editing ? `${copy.edit} ${editing}` : copy.add}</h2>
      <div className="model-form">
        <label><span>{copy.alias}</span><input value={form.alias} disabled={Boolean(editing)} placeholder="production" onChange={(event) => patch({ alias: event.target.value })} /></label>
        <label><span>{copy.base}</span><input value={form.api_base} placeholder="https://example.com/v1" onChange={(event) => patch({ api_base: event.target.value })} /></label>
        <label><span>{copy.model}</span><input value={form.model_name} placeholder="gpt-4.1-mini" onChange={(event) => patch({ model_name: event.target.value })} /></label>
        <label><span>{editing ? copy.replaceKey : copy.key}</span><input type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => patch({ api_key: event.target.value })} /></label>
        <label><span>{copy.temperature}</span><input type="number" min="0" max="2" step="0.1" value={form.temperature} onChange={(event) => patch({ temperature: event.target.value })} /></label>
        <label className="model-enabled"><input type="checkbox" checked={form.enabled} onChange={(event) => patch({ enabled: event.target.checked })} />{copy.enabled}</label>
      </div>
      <div className="actions"><button type="button" className="primary" disabled={!encryptionReady || !form.alias || !form.api_base || !form.model_name || (!editing && !form.api_key)} onClick={() => void submit()}>{editing ? copy.save : copy.add}</button>{editing ? <button type="button" className="secondary-command" onClick={() => { setEditing(null); setForm(emptyForm()); }}>{copy.cancel}</button> : null}</div>
    </section>
    <section className="model-list"><h2>{copy.configured}</h2>
      {!models.length ? <p className="muted">{copy.empty}</p> : <table className="config-table"><thead><tr><th>{copy.alias}</th><th>{copy.model}</th><th>{copy.base}</th><th>{copy.enabled}</th><th>{copy.date}</th><th /></tr></thead><tbody>{models.map((model) => <tr key={model.alias}><td><code>{model.alias}</code></td><td>{model.model_name}</td><td><code>{model.api_base}</code></td><td>{model.enabled ? model.runtime_ready ? copy.available : copy.unavailable : copy.disabled}{model.key_configured ? ` · ${copy.keyConfigured}` : ""}</td><td>{model.updated_at ? new Date(model.updated_at).toLocaleString() : "-"}</td><td className="model-actions"><button type="button" className="text-command" onClick={() => startEdit(model)}>{copy.edit}</button><button type="button" className="text-command delete-command" onClick={() => void remove(model.alias)}>{copy.remove}</button></td></tr>)}</tbody></table>}
    </section>
  </main>;
}
