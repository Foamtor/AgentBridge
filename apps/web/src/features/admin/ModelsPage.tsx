import { useEffect, useState } from "react";
import { useI18n } from "../../i18n";
import { adminErrorMessage, adminFetch, type AdminRequestError } from "./adminFetch";

type Model = {
  alias: string;
  api_base: string;
  model_name: string;
  temperature: number;
  enabled: boolean;
  key_configured: boolean;
  runtime_ready: boolean;
  last_test_status?: "success" | "failed" | null;
  last_test_latency_ms?: number | null;
  last_test_error?: string | null;
  last_test_capability?: string | null;
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
    title: "Model management", intro: "Configure OpenAI-compatible models. API keys are submitted only when saved, encrypted in PostgreSQL, and never returned to the console.", missingTitle: "Model credential encryption is not configured", missingSetup: "Generate a key here, or paste an existing Fernet key. The value is written only to the mounted .env file and is never stored in PostgreSQL.", missingRestart: "The key becomes active immediately. Restart the API after saving so it is recovered after a container replacement. Back it up; losing it makes saved credentials unrecoverable.", containerSetup: "This API is containerized without a persistent environment-file mount. Set the key in the deployment secret store or host environment instead.", currentPassword: "Confirm current password", existingKey: "Encryption key (paste or generate)", generateKey: "Generate random key", saveKey: "Save encryption key", keySaved: "Encryption key saved and active. Back it up, then restart the API when convenient.", keySaveError: "Could not save the key. Generate a new key or paste a valid Fernet key, and confirm the mounted .env is writable.", add: "Add model", edit: "Edit", alias: "Alias", base: "API base", model: "Model name", key: "API key", replaceKey: "Replace API key (blank keeps it)", temperature: "Temperature", enabled: "Enable for the verification workbench", save: "Save changes", cancel: "Cancel", configured: "Configured models", empty: "No models configured. Fake demo remains available in the verification workbench.", loaded: "Loaded", unavailable: "Credential unavailable", disabled: "Disabled", keyConfigured: "key configured", test: "Test connection and tool calling", testing: "Testing…", testPassed: "Connection and tool calling passed", testNeedsRefresh: "Run the new tool-call test", testFailed: "Tool calling test failed", toolCallHint: "The provider rejected the tool-call test request or did not return a tool call. This does not by itself prove the model lacks tool calling.", connectionTestError: "The model endpoint could not complete the basic connection check. Check the API address, network access, API key, and model name.", saved: "Model saved. The key will not be shown again.", updated: "Model updated.", remove: "Delete", confirm: "Delete model alias", date: "Updated",
  } : {
    title: "模型管理", intro: "配置 OpenAI 兼容模型。API Key 仅在保存时提交，数据库只保存加密密文，控制台不会返回明文。", missingTitle: "尚未配置模型凭据加密密钥", missingSetup: "可在这里生成密钥，也可以粘贴已有 Fernet 密钥。密钥只写入挂载的 .env 文件，不会保存到 PostgreSQL。", missingRestart: "保存后会立即在当前 API 生效。为保证容器替换后仍能恢复，请备份密钥，并在方便时重启 API。密钥丢失后，已保存的模型凭据无法恢复。", containerSetup: "当前 API 运行在容器中，且没有持久化的环境文件挂载。请改在部署密钥管理或宿主机环境中设置该密钥。", currentPassword: "确认当前密码", existingKey: "加密密钥（可粘贴或生成）", generateKey: "生成随机密钥", saveKey: "保存加密密钥", keySaved: "加密密钥已保存并在当前 API 生效。请备份密钥，并在方便时重启 API。", keySaveError: "密钥保存失败。请点击“生成随机密钥”或粘贴有效 Fernet 密钥，并确认挂载的 .env 可写。", add: "添加模型", edit: "编辑", alias: "别名", base: "API 地址", model: "模型名称", key: "API Key", replaceKey: "替换 API Key（留空则保留）", temperature: "温度", enabled: "启用并用于验证工作台", save: "保存变更", cancel: "取消", configured: "已配置模型", empty: "尚未配置模型。Fake 演示仍可在验证工作台中运行。", loaded: "已加载", unavailable: "凭据不可用", disabled: "已停用", keyConfigured: "密钥已配置", test: "测试连接与工具调用", testing: "正在测试…", testPassed: "连接和工具调用已通过", testNeedsRefresh: "需要重新执行工具调用测试", testFailed: "工具调用测试未通过", toolCallHint: "模型服务拒绝了工具调用测试请求，或没有返回工具调用。这并不能单独证明模型不支持工具调用。", connectionTestError: "模型服务没有完成基础连接检查。请检查 API 地址、网络连通性、API Key 和模型名称。", saved: "模型配置已保存。密钥不会再次显示。", updated: "模型配置已更新。", remove: "删除", confirm: "删除模型别名", date: "更新时间",
  };
  const [models, setModels] = useState<Model[]>([]);
  const [encryptionReady, setEncryptionReady] = useState(false);
  const [keySetupAvailable, setKeySetupAvailable] = useState(true);
  const [form, setForm] = useState<Form>(emptyForm);
  const [encryptionPassword, setEncryptionPassword] = useState("");
  const [encryptionKey, setEncryptionKey] = useState("");
  const [savingEncryptionKey, setSavingEncryptionKey] = useState(false);
  const [testingAlias, setTestingAlias] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const patch = (next: Partial<Form>) => setForm((current) => ({ ...current, ...next }));
  const validationMessages = locale === "en"
    ? { alias: "Use 1-64 letters, numbers, spaces, dots, _ or -. Do not use path separators.", api_base: "API base must be an absolute HTTP(S) URL without credentials or query parameters.", model_name: "Model name is required.", api_key: "API key is required.", temperature: "Temperature must be between 0 and 2." }
    : { alias: "可使用中英文、数字、空格、点号、下划线和短横线，长度 1 到 64；不能使用路径分隔符。", api_base: "API 地址必须是完整的 HTTP(S) 地址，且不能包含账号、密码或查询参数。", model_name: "模型名称不能为空。", api_key: "API Key 不能为空。", temperature: "温度必须在 0 到 2 之间。" };

  function connectionReason(reason: string | undefined): string {
    if (reason === "connection_http_401" || reason === "connection_http_403") return locale === "en" ? "The provider rejected the API key or account permission." : "模型服务拒绝了 API Key 或账号权限，请确认密钥和账户权限。";
    if (reason === "connection_http_404") return locale === "en" ? "The provider endpoint or model was not found. Check the API base and model name." : "模型服务找不到接口或模型，请确认 API 地址和模型名称。";
    if (reason === "connection_http_429") return locale === "en" ? "The provider rate limit was reached. Try again later." : "模型服务触发了限流，请稍后重试。";
    if (/^connection_http_5\d\d$/.test(reason ?? "")) return locale === "en" ? "The provider returned a temporary server error. Try again later." : "模型服务暂时返回服务端错误，请稍后重试。";
    return copy.connectionTestError;
  }

  const load = async () => {
    try {
      const body = await adminFetch<{ models: Model[]; encryption_ready: boolean; key_setup_available?: boolean }>("/admin/models");
      setModels(body.models);
      setEncryptionReady(body.encryption_ready);
      setKeySetupAvailable(body.key_setup_available !== false);
      setError(null);
    } catch (reason) {
      setError(adminErrorMessage(reason, locale));
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
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        await adminFetch("/admin/models", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...payload, alias: form.alias, api_key: form.api_key }),
        });
      }
      setMessage(editing ? copy.updated : copy.saved);
      setEditing(null);
      setForm(emptyForm());
      await load();
    } catch (reason) {
      const requestError = reason as AdminRequestError;
      const field = requestError.field as keyof typeof validationMessages | undefined;
      setError(requestError.status === 422 && field && validationMessages[field] ? validationMessages[field] : adminErrorMessage(reason, locale));
    }
  }

  async function saveEncryptionKey() {
    setError(null);
    setMessage(null);
    setSavingEncryptionKey(true);
    try {
      await adminFetch<{ configured: boolean; runtime_ready: boolean; restart_required: boolean }>("/admin/models/encryption-key", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: encryptionPassword,
          ...(encryptionKey.trim() ? { encryption_key: encryptionKey.trim() } : {}),
        }),
      });
      setEncryptionPassword("");
      setEncryptionKey("");
      setEncryptionReady(true);
      setMessage(copy.keySaved);
    } catch (reason) {
      const status = (reason as { status?: number }).status;
      setError(status === 422 ? copy.keySaveError : adminErrorMessage(reason, locale));
    } finally {
      setSavingEncryptionKey(false);
    }
  }

  function generateEncryptionKey() {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    setEncryptionKey(window.btoa(binary).replace(/\+/g, "-").replace(/\//g, "_"));
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
      setError(adminErrorMessage(reason, locale));
    }
  }

  async function testConnection(alias: string) {
    setError(null);
    setMessage(null);
    setTestingAlias(alias);
    try {
      await adminFetch(`/admin/models/${encodeURIComponent(alias)}/test`, { method: "POST" });
      await load();
    } catch (reason) {
      const requestError = reason as AdminRequestError;
      const code = requestError.code;
      setError(
        code === "model_tool_call_test_failed" || code === "model_tool_call_test_timeout"
          ? copy.toolCallHint
          : code === "model_connection_test_failed" || code === "model_connection_test_timeout"
            ? connectionReason(requestError.reason)
            : adminErrorMessage(reason, locale),
      );
    } finally {
      setTestingAlias(null);
    }
  }

  function modelStatus(model: Model) {
    if (!model.enabled) return copy.disabled;
    if (!model.runtime_ready) return copy.unavailable;
    const test = model.last_test_status === "success" && model.last_test_capability === "tool_calling_v1"
      ? `${copy.testPassed}${typeof model.last_test_latency_ms === "number" ? `（${model.last_test_latency_ms} ms）` : ""}`
      : model.last_test_status === "success" ? copy.testNeedsRefresh
      : model.last_test_status === "failed" ? copy.testFailed : "";
    return `${copy.loaded}${test ? ` · ${test}` : ""}${model.key_configured ? ` · ${copy.keyConfigured}` : ""}`;
  }

  function testFailureHint(model: Model) {
    return model.last_test_status === "failed" && model.last_test_error?.startsWith("tool_call_")
      ? copy.toolCallHint
      : null;
  }

  return <main className="page models-page">
    <header><h1>{copy.title}</h1><p className="lede">{copy.intro}</p></header>
    {!encryptionReady ? <aside className="model-key-warning" role="alert">
      <strong>{copy.missingTitle}</strong>
      <p>{copy.missingSetup}</p>
      <code>python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</code>
      <p>{copy.missingRestart}</p>
      {!keySetupAvailable ? <p>{copy.containerSetup}</p> : <div className="model-key-form">
        <label><span>{copy.currentPassword}</span><input type="password" autoComplete="current-password" value={encryptionPassword} onChange={(event) => setEncryptionPassword(event.target.value)} /></label>
        <label><span>{copy.existingKey}</span><input type="text" spellCheck={false} autoComplete="off" value={encryptionKey} onChange={(event) => setEncryptionKey(event.target.value)} /></label>
        <div className="actions"><button type="button" className="secondary-command" onClick={generateEncryptionKey}>{copy.generateKey}</button><button type="button" className="primary" disabled={savingEncryptionKey || !encryptionPassword || !encryptionKey.trim()} onClick={() => void saveEncryptionKey()}>{copy.saveKey}</button></div>
      </div>}
    </aside> : null}
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
      {!models.length ? <p className="muted">{copy.empty}</p> : <table className="config-table"><thead><tr><th>{copy.alias}</th><th>{copy.model}</th><th>{copy.base}</th><th>{copy.enabled}</th><th>{copy.date}</th><th /></tr></thead><tbody>{models.map((model) => <tr key={model.alias}><td><code>{model.alias}</code></td><td>{model.model_name}</td><td><code>{model.api_base}</code></td><td>{modelStatus(model)}{testFailureHint(model) ? <small className="model-test-hint">{testFailureHint(model)}</small> : null}</td><td>{model.updated_at ? new Date(model.updated_at).toLocaleString() : "-"}</td><td className="model-actions"><button type="button" className="text-command" disabled={!model.enabled || testingAlias === model.alias} onClick={() => void testConnection(model.alias)}>{testingAlias === model.alias ? copy.testing : copy.test}</button><button type="button" className="text-command" onClick={() => startEdit(model)}>{copy.edit}</button><button type="button" className="text-command delete-command" onClick={() => void remove(model.alias)}>{copy.remove}</button></td></tr>)}</tbody></table>}
    </section>
  </main>;
}
