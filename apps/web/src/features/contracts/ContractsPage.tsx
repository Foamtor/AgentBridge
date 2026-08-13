import { useI18n } from "../../i18n";

type Example = Record<string, unknown>;

type EventSpec = {
  type: string;
  title: string;
  when: string;
  action: string;
  fields: string;
  example: Example;
};

const stableEvents: EventSpec[] = [
  {
    type: "start",
    title: "开始一次运行",
    when: "服务接受请求并创建 run 后发送。",
    action: "记录 run_id、route 和 thread_id，开始接收后续事件。",
    fields: "data.thread_id, data.route",
    example: { type: "start", run_id: "r-abc", event_id: "r-abc-1", sequence: 1, data: { thread_id: "t-demo-001", route: "echo" } },
  },
  {
    type: "step_update",
    title: "流程节点状态变化",
    when: "业务图进入或离开一个流程节点时发送。",
    action: "在调试界面显示当前节点和 running / completed 等状态。",
    fields: "step, status",
    example: { type: "step_update", run_id: "r-abc", event_id: "r-abc-2", sequence: 2, step: "echo_node", status: "running", data: {} },
  },
  {
    type: "text_delta",
    title: "模型回复片段",
    when: "模型产生一段可展示文本时发送，多个片段需要按顺序拼接。",
    action: "将 data.content 追加到回复区域，不要把每个片段当成独立消息。",
    fields: "data.content, data.agent_id?",
    example: { type: "text_delta", run_id: "r-abc", event_id: "r-abc-3", sequence: 3, data: { content: "你好", agent_id: "assistant" } },
  },
  {
    type: "tool_call",
    title: "准备调用工具",
    when: "模型或流程决定调用一个业务工具时发送。",
    action: "展示工具名和参数，并等待对应的 tool_result。",
    fields: "data.name, data.args, data.tool_call_id",
    example: { type: "tool_call", run_id: "r-abc", event_id: "r-abc-4", sequence: 4, data: { name: "list_work_orders", args: {}, tool_call_id: "tc-1" } },
  },
  {
    type: "tool_result",
    title: "工具返回结果",
    when: "工具执行完成后发送。",
    action: "把结果与同一个 tool_call_id 关联，失败时显示 ok=false 和 summary。",
    fields: "data.name, data.ok, data.tool_call_id, data.summary",
    example: { type: "tool_result", run_id: "r-abc", event_id: "r-abc-5", sequence: 5, data: { name: "list_work_orders", ok: true, tool_call_id: "tc-1", summary: "返回 3 条工单" } },
  },
  {
    type: "done",
    title: "运行成功结束",
    when: "流程正常完成时发送。",
    action: "将运行状态标记为完成；业务结果应从之前的事件中读取。",
    fields: "无额外必填字段",
    example: { type: "done", run_id: "r-abc", event_id: "r-abc-6", sequence: 6, data: {} },
  },
  {
    type: "error",
    title: "运行失败",
    when: "流程或工具无法继续时发送。",
    action: "显示错误 message 和 code，同时保留已经收到的前置事件。",
    fields: "data.message, data.code",
    example: { type: "error", run_id: "r-abc", event_id: "r-abc-7", sequence: 7, data: { message: "tool failed", code: "tool_error" } },
  },
  {
    type: "cancel_requested",
    title: "收到取消请求",
    when: "客户端调用 POST /chat/cancel 后发送。",
    action: "将界面标记为取消中；取消是协作式的，不代表副作用立即停止。",
    fields: "data.thread_id, data.run_id",
    example: { type: "cancel_requested", run_id: "r-abc", event_id: "r-abc-8", sequence: 8, data: { thread_id: "t-demo-001", run_id: "r-abc" } },
  },
  {
    type: "cancelled",
    title: "运行已取消",
    when: "平台确认运行停止后发送。",
    action: "将运行状态标记为已取消，并允许用户重新发起请求。",
    fields: "data.thread_id, data.run_id",
    example: { type: "cancelled", run_id: "r-abc", event_id: "r-abc-9", sequence: 9, data: { thread_id: "t-demo-001", run_id: "r-abc" } },
  },
];

const extensionEvents: EventSpec[] = [
  {
    type: "x.bridge.model_usage",
    title: "模型用量记录",
    when: "模型调用完成并返回 token 用量时发送。",
    action: "用于用量统计和成本分析；不要把它当成业务回复展示给用户。",
    fields: "data.input_tokens, data.output_tokens, data.total_tokens?",
    example: { type: "x.bridge.model_usage", data: { input_tokens: 120, output_tokens: 48, total_tokens: 168 } },
  },
  {
    type: "x.bridge.prompt",
    title: "实际使用的提示词版本",
    when: "平台为运行解析出可审计的提示词来源时发送。",
    action: "在调试和审计场景展示 prompt 名称、来源和版本；不要暴露敏感提示词正文。",
    fields: "data.prompts[].name, data.prompts[].source, data.prompts[].version",
    example: { type: "x.bridge.prompt", data: { prompts: [{ name: "work_order_ops.planner", source: "platform", version: 3 }] } },
  },
  {
    type: "x.work_order_ops.list",
    title: "工单列表业务结果",
    when: "工单插件完成列表查询后发送。",
    action: "按 data.columns 渲染表格，按 data.rows 展示数据；不要猜字段。",
    fields: "data.schema_version, data.columns, data.rows, data.total",
    example: { type: "x.work_order_ops.list", data: { schema_version: 1, resource: "work_orders", columns: [{ key: "id", label: "工单号", data_type: "string" }], rows: [{ id: "WO-001" }], total: 1, truncated: false } },
  },
  {
    type: "x.work_order_ops.chart",
    title: "工单统计图表",
    when: "工单插件完成状态统计后发送。",
    action: "优先使用 data.echarts_option；不支持图表库时退化显示 categories 和 series.data。",
    fields: "data.chart_type, data.x_axis.categories, data.series, data.echarts_option",
    example: { type: "x.work_order_ops.chart", data: { schema_version: 1, chart_type: "bar", x_axis: { categories: ["open"] }, series: [{ name: "工单数", data: [1] }] } },
  },
  {
    type: "x.bridge.citation",
    title: "知识检索引用",
    when: "检索工具返回可引用的知识片段后发送。",
    action: "展示来源和引用内容，并保留 doc_id / chunk_id 供追溯。",
    fields: "data.citations[].doc_id, data.citations[].chunk_id, data.citations[].text",
    example: { type: "x.bridge.citation", data: { citations: [{ doc_id: "sop-001", chunk_id: "sop-001-3", text: "处理规范片段" }] } },
  },
  {
    type: "x.bridge.approval_required",
    title: "需要人工审批",
    when: "业务插件准备执行有副作用的写操作时发送。",
    action: "暂停写入并展示审批内容；批准后调用 POST /approvals/{approval_id}。",
    fields: "data.tool, data.timeout_seconds, data.action.payload",
    example: { type: "x.bridge.approval_required", data: { tool: "create_work_order", timeout_seconds: 1800, action: { type: "work_order_ops.create_v1", payload: { title: "网络跟进" } } } },
  },
  {
    type: "x.work_order_ops.work_order_created",
    title: "审批后的创建结果",
    when: "审批通过且工单和台账写入成功后发送。",
    action: "展示最终编号和状态；使用 approval_id 保证重复审批不会重复创建。",
    fields: "data.work_order_id, data.ledger_id, data.status",
    example: { type: "x.work_order_ops.work_order_created", data: { schema_version: 1, work_order_id: "WO-001", ledger_id: "LG-001", status: "open" } },
  },
];

const envelopeFields = [
  ["type", "事件名称；稳定事件不带 x.，插件扩展必须以 x.<domain>. 开头。"],
  ["run_id", "本次运行的唯一标识。"],
  ["event_id", "事件唯一标识，通常为 run_id-sequence。"],
  ["sequence", "同一运行内递增序号；客户端应按它排序并去重。"],
  ["trace_id", "可选的链路追踪标识。"],
  ["timestamp", "毫秒级 Unix 时间戳。"],
  ["step / status", "可选的流程节点和状态字段。"],
  ["data", "事件类型对应的业务载荷。"],
];

function ExampleBlock({ value }: { value: Example }) {
  return <pre className="contract-code"><code>{JSON.stringify(value, null, 2)}</code></pre>;
}

function EventSpecBlock({ spec, english }: { spec: EventSpec; english: boolean }) {
  return <article className="contract-event">
    <header><div><code>{spec.type}</code><h3>{english ? spec.type : spec.title}</h3></div><span>{english ? "event" : "事件"}</span></header>
    <dl className="contract-event-facts">
      <div><dt>{english ? "When" : "什么时候出现"}</dt><dd>{english ? "When this event is emitted during a run." : spec.when}</dd></div>
      <div><dt>{english ? "What to do" : "客户端怎么处理"}</dt><dd>{english ? "Use this event to update the corresponding run or business view." : spec.action}</dd></div>
      <div><dt>{english ? "Important fields" : "重点字段"}</dt><dd><code>{spec.fields}</code></dd></div>
    </dl>
    <details><summary>{english ? "View JSON example" : "查看 JSON 示例"}</summary><ExampleBlock value={spec.example} /></details>
  </article>;
}

export function ContractsPage() {
  const { locale } = useI18n();
  const english = locale === "en";
  const text = english ? {
    title: "API contracts", intro: "This page explains the shapes exchanged between your application, AgentBridge, and a plugin. A contract is an interface rule: it defines the request, the event envelope, and the business payload.", flowTitle: "One request, one stream", flow: ["POST /chat/stream sends a question and selects a plugin.", "The server returns SSE lines. Each line contains one JSON event.", "Stable platform events describe progress; x.* events carry plugin business results.", "The stream ends with done, error, or cancelled."], httpTitle: "HTTP interfaces", requestTitle: "Start a conversation", requestNote: "Use this endpoint when your application wants to run a plugin. route is the registered plugin name.", cancelTitle: "Cancel a run", cancelNote: "Cancellation is cooperative. A running tool may finish before the platform stops the run.", envelopeTitle: "Shared SSE event envelope", envelopeNote: "Every SSE event has these fields. The event-specific payload lives in data.", stableTitle: "Platform events", stableNote: "These nine types are stable and can be handled by every client.", extensionTitle: "Extensions: platform and plugin events", extensionNote: "Extensions use x.<domain>.<event>. AgentBridge may emit x.bridge.* platform evidence; a plugin owns its x.<domain>.* business results. Unknown extensions should be ignored so older clients remain compatible.", json: "JSON example", field: "Field", meaning: "Meaning", method: "Method", path: "Path", response: "Response", request: "Request body", readDocs: "Full specification: docs/contracts.md"
  } : {
    title: "接口规范", intro: "这里说明业务应用、AgentBridge 平台和业务插件之间交换的数据长什么样。“接口规范”就是接口契约：约定请求怎么发、流式事件有哪些公共字段、业务结果放在哪里。", flowTitle: "一次请求如何完成", flow: ["业务应用调用 POST /chat/stream，提交问题并指定插件。", "服务端返回 SSE 流，每一行都是一个 JSON 事件。", "平台事件描述运行进度；x.* 事件承载插件的业务结果。", "最后以 done、error 或 cancelled 表示本次运行结束。"], httpTitle: "HTTP 接口", requestTitle: "发起一次对话", requestNote: "业务应用要运行插件时调用此接口。route 是已经注册的插件名称。", cancelTitle: "取消一次运行", cancelNote: "取消是协作式的；正在执行的工具可能先完成，再停止运行。", envelopeTitle: "SSE 公共事件格式", envelopeNote: "每条 SSE 事件都有这些字段，具体业务内容放在 data 里。", stableTitle: "平台事件", stableNote: "这 9 类事件由平台统一发送，所有客户端都可以按同一规则处理。", extensionTitle: "扩展事件：平台与插件", extensionNote: "扩展事件使用 x.<domain>.<event> 格式。AgentBridge 发送 x.bridge.* 平台证据；业务插件负责自己的 x.<domain>.* 业务结果。客户端遇到不认识的扩展事件应忽略，以保持兼容。", json: "JSON 示例", field: "字段", meaning: "含义", method: "方法", path: "路径", response: "响应", request: "请求体", readDocs: "完整规范见 docs/contracts.md"
  };
  return <ContractLayout english={english} text={text} />;
}

function ContractLayout({ english, text }: { english: boolean; text: Record<string, string | string[]> }) {
  const flow = text.flow as string[];
  return <main className="page contracts-page">
    <header className="contracts-header"><p className="eyebrow">AgentBridge / {english ? "REFERENCE" : "开发参考"}</p><h1>{text.title}</h1><p className="lede">{text.intro}</p></header>
    <section className="contracts-section contracts-flow"><div className="contracts-section-heading"><h2>{text.flowTitle}</h2></div><ol>{flow.map((item, index) => <li key={item}><b>{String(index + 1).padStart(2, "0")}</b><span>{item}</span></li>)}</ol></section>
    <section className="contracts-section"><div className="contracts-section-heading"><div><h2>{text.httpTitle}</h2><p>{text.requestTitle}：{text.requestNote}</p></div></div><div className="contract-http-grid"><article className="contract-http"><header><strong>{text.requestTitle}</strong><span>POST</span></header><code>/chat/stream</code><p>{text.request}</p><ExampleBlock value={{ query: "show work orders", thread_id: "t-demo-001", route: "work_order_ops", model: "default", extra: {} }} /><details><summary>{text.response}</summary><ExampleBlock value={{ type: "start", run_id: "r-abc", event_id: "r-abc-1", sequence: 1, data: { thread_id: "t-demo-001", route: "work_order_ops" } }} /></details></article><article className="contract-http"><header><strong>{text.cancelTitle}</strong><span>POST</span></header><code>/chat/cancel</code><p>{text.cancelNote}</p><ExampleBlock value={{ thread_id: "t-demo-001", run_id: "r-abc" }} /></article></div></section>
    <section className="contracts-section"><div className="contracts-section-heading"><div><h2>{text.envelopeTitle}</h2><p>{text.envelopeNote}</p></div></div><div className="contract-envelope"><div className="contract-field-table"><div className="contract-field-row contract-field-head"><strong>{text.field}</strong><strong>{text.meaning}</strong></div>{envelopeFields.map(([field, meaning]) => <div className="contract-field-row" key={field}><code>{field}</code><span>{english ? field === "type" ? "Event name." : field === "run_id" ? "Unique id for this run." : field === "event_id" ? "Unique event id." : field === "sequence" ? "Increasing sequence used to order and deduplicate." : field === "trace_id" ? "Optional tracing id." : field === "timestamp" ? "Unix timestamp in milliseconds." : field === "step / status" ? "Optional node and state fields." : "Event-specific payload." : meaning}</span></div>)}</div><ExampleBlock value={{ type: "tool_call", run_id: "r-abc", event_id: "r-abc-4", sequence: 4, trace_id: "tr-xyz", timestamp: 1721721600300, data: { name: "list_work_orders", args: {}, tool_call_id: "tc-1" } }} /></div></section>
    <section className="contracts-section"><div className="contracts-section-heading"><div><h2>{text.stableTitle}</h2><p>{text.stableNote}</p></div></div><div className="contract-event-list">{stableEvents.map((spec) => <EventSpecBlock key={spec.type} spec={spec} english={english} />)}</div></section>
    <section className="contracts-section"><div className="contracts-section-heading"><div><h2>{text.extensionTitle}</h2><p>{text.extensionNote}</p></div></div><div className="contract-event-list">{extensionEvents.map((spec) => <EventSpecBlock key={spec.type} spec={spec} english={english} />)}</div></section>
    <footer className="contracts-footer"><code>{text.readDocs}</code></footer>
  </main>;
}
