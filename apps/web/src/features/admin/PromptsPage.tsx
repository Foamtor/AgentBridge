import { useEffect, useState } from "react";
import { adminFetch } from "./adminFetch";

type PromptItem = { name: string };

export function PromptsPage() {
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
    void reload().catch((err) => setError(String(err)));
  }, []);

  async function onSave() {
    setError(null);
    setMessage(null);
    try {
      await adminFetch(`/prompts/${encodeURIComponent(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setMessage("已保存草稿");
      await reload();
    } catch (err) {
      setError(String(err));
    }
  }

  async function onPublish() {
    setError(null);
    setMessage(null);
    try {
      await adminFetch(`/prompts/${encodeURIComponent(name)}/publish`, {
        method: "POST",
      });
      setMessage("已发布");
      await reload();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <main className="page">
      <header>
        <h1>Prompts</h1>
        <p className="lede">平台 Prompt 覆盖（C2）；发布后优先于插件目录文件。</p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {message ? <p className="muted">{message}</p> : null}
      <div className="session-bar">
        <label>
          name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
      </div>
      <label>
        content
        <textarea rows={6} value={content} onChange={(e) => setContent(e.target.value)} />
      </label>
      <div className="actions">
        <button type="button" onClick={() => void onSave()}>
          保存
        </button>
        <button type="button" onClick={() => void onPublish()}>
          发布
        </button>
      </div>
      <h2>已登记 Prompt</h2>
      <ul className="timeline">
        {items.map((item) => (
          <li key={item.name}>{item.name}</li>
        ))}
      </ul>
    </main>
  );
}
