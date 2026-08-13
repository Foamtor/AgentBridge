import { useEffect, useState } from "react";
import { adminErrorMessage, adminFetch } from "./adminFetch";
import { useI18n } from "../../i18n";

type PromptItem = { name: string };

export function PromptsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? { title: "Prompt management", intro: "Save a draft, then publish it to change model behavior in the real work-order planner. Drafts never affect runs.", impact: "Publishing changes live model behavior for the registered flow and is recorded in the audit log.", name: "Prompt name", content: "Content", save: "Save draft", publish: "Publish", registered: "Registered prompts", saved: "Draft saved", published: "Published", loading: "Loading…", error: "Could not load prompt settings.", confirm: "Publish this prompt to the live flow?" } : { title: "提示词管理", intro: "先保存草稿，再发布到真实工单规划流程；草稿不会影响运行。", impact: "发布会改变登记业务流程的真实模型行为，并记录到审计日志。", name: "提示词名称", content: "内容", save: "保存草稿", publish: "发布", registered: "已登记提示词", saved: "草稿已保存", published: "已发布", loading: "加载中…", error: "无法读取提示词配置。", confirm: "确定要把这个提示词发布到真实业务流程吗？" };
  const [items, setItems] = useState<PromptItem[]>([]);
  const [name, setName] = useState("demo_prompt");
  const [content, setContent] = useState("hello {name}");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function reload() {
    const body = await adminFetch<{ items: PromptItem[] }>("/prompts");
    setItems(body.items);
  }

  useEffect(() => {
    void reload().catch((err) => setError(adminErrorMessage(err, locale)));
  }, [locale]);

  async function onSave() {
    setError(null);
    setMessage(null);
    try {
      await adminFetch(`/prompts/${encodeURIComponent(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setMessage(copy.saved);
      await reload();
    } catch (err) {
      setError(adminErrorMessage(err, locale));
    }
  }

  async function onPublish() {
    if (!window.confirm(copy.confirm)) return;
    setError(null);
    setMessage(null);
    try {
      await adminFetch(`/prompts/${encodeURIComponent(name)}/publish`, {
        method: "POST",
      });
      setMessage(copy.published);
      await reload();
    } catch (err) {
      setError(adminErrorMessage(err, locale));
    }
  }

  return (
    <main className="page admin-subpage prompts-page">
      <header className="admin-page-header">
        <h1>{copy.title}</h1>
        <p className="lede">{copy.intro}</p>
      </header>
      <p className="admin-alert" role="note">{copy.impact}</p>
      {error ? <p className="error">{error}</p> : null}
      {message ? <p className="muted">{message}</p> : null}
      <div className="admin-editor-form">
        <label>
          <span>{copy.name}</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="admin-editor-content">
          <span>{copy.content}</span>
          <textarea rows={8} value={content} onChange={(e) => setContent(e.target.value)} />
        </label>
        <div className="actions admin-editor-actions">
          <button type="button" onClick={() => void onSave()}>
            {copy.save}
          </button>
          <button type="button" className="secondary-command" onClick={() => void onPublish()}>
            {copy.publish}
          </button>
        </div>
      </div>
      <h2>{copy.registered}</h2>
      <ul className="timeline">
        {items.map((item) => (
          <li key={item.name}>{item.name}</li>
        ))}
      </ul>
    </main>
  );
}
