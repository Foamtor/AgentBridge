import { useEffect, useState } from "react";
import { adminErrorMessage, adminFetch } from "./adminFetch";
import { useI18n } from "../../i18n";

type PromptItem = { name: string };

export function PromptsPage() {
  const { locale } = useI18n();
  const copy = locale === "en" ? { title: "Prompt overrides", intro: "Save a draft, then publish it to make it active in the real work-order planner. Drafts never affect runs.", name: "Prompt name", content: "Content", save: "Save draft", publish: "Publish", registered: "Registered prompts", saved: "Draft saved", published: "Published", loading: "Loading…", error: "Could not load prompt settings." } : { title: "提示词覆盖", intro: "先保存草稿，再发布到真实工单规划流程；草稿不会影响运行。", name: "提示词名称", content: "内容", save: "保存草稿", publish: "发布", registered: "已登记提示词", saved: "草稿已保存", published: "已发布", loading: "加载中…", error: "无法读取提示词配置。" };
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
    <main className="page">
      <header>
        <h1>{copy.title}</h1>
        <p className="lede">{copy.intro}</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {message ? <p className="muted">{message}</p> : null}
      <div className="session-bar">
        <label>
          {copy.name}
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
      </div>
      <label>
        {copy.content}
        <textarea rows={6} value={content} onChange={(e) => setContent(e.target.value)} />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void onSave()}>
          {copy.save}
        </button>
        <button type="button" onClick={() => void onPublish()}>
          {copy.publish}
        </button>
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
