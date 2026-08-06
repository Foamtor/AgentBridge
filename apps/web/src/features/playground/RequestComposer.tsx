import type { PlaygroundCopy } from "./copy";
import type { ChatRequest } from "./types";

type RouteOption = { name: string; description: string };

type Props = {
  copy: PlaygroundCopy;
  request: ChatRequest;
  extraText: string;
  routes: RouteOption[];
  models: Array<{ alias: string; model_name?: string; kind?: string }>;
  busy: boolean;
  error: string | null;
  copied: boolean;
  extraValid: boolean;
  onRequest: (request: ChatRequest) => void;
  onExtraText: (value: string) => void;
  onSend: () => void;
  onCancel: () => void;
  onDoubleFire: () => void;
  onNewThread: () => void;
  onLoad: () => void;
  onCopyCurl: () => void;
  canLoad: boolean;
};

export function RequestComposer(props: Props) {
  const { copy, request } = props;
  const patch = (next: Partial<ChatRequest>) => props.onRequest({ ...request, ...next });
  const selectedRoute = props.routes.find((route) => route.name === request.route);
  return <section className="composer-zone">
    <div className="section-title"><h2>{copy.request}</h2><div className="quiet-actions">
      <button type="button" className="text-command" onClick={props.onNewThread}>{copy.newThread}</button>
      <button type="button" className="text-command" onClick={props.onLoad} disabled={!props.canLoad}>{copy.replay}</button>
      <button type="button" className="text-command" onClick={props.onCopyCurl}>{props.copied ? copy.copied : copy.copyCurl}</button>
    </div></div>
    <div className="request-fields">
      <label><span>{copy.route}</span><select value={request.route} onChange={(event) => patch({ route: event.target.value })}>
        {props.routes.map((route) => <option value={route.name} key={route.name}>{copy.routeName(route.name, route.description)} ({route.name})</option>)}
        {!props.routes.some((route) => route.name === request.route) ? <option value={request.route}>{copy.routeName(request.route)} ({request.route})</option> : null}
      </select></label>
      <label><span>{copy.thread}</span><input value={request.thread_id} onChange={(event) => patch({ thread_id: event.target.value })} /></label>
      <label><span>{copy.model}</span><select value={request.model} onChange={(event) => patch({ model: event.target.value })}><option value="default">default · Fake / environment</option>{props.models.map((model) => <option value={model.alias} key={model.alias}>{model.alias}{model.model_name ? ` · ${model.model_name}` : ""}</option>)}{request.model !== "default" && !props.models.some((model) => model.alias === request.model) ? <option value={request.model}>{request.model}</option> : null}</select></label>
    </div>
    <p className="route-hint">{selectedRoute?.description || copy.routeHint}</p>
    <label className="query-field"><span>{copy.query}<small>{copy.queryHint}</small></span><textarea rows={4} value={request.query} onChange={(event) => patch({ query: event.target.value })} onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !props.busy && request.query.trim()) { event.preventDefault(); props.onSend(); } if (event.key === "Escape" && props.busy) { event.preventDefault(); props.onCancel(); } }} /></label>
    <details className="request-advanced"><summary>{copy.advanced}</summary><label><span>{copy.extra}</span><textarea className="json-editor" rows={6} spellCheck={false} value={props.extraText} aria-invalid={!props.extraValid} onChange={(event) => props.onExtraText(event.target.value)} /></label>{!props.extraValid ? <p className="composer-error">{copy.invalidJson}</p> : null}</details>
    {props.error ? <p className="composer-error" role="alert">{props.error}</p> : null}
    <div className="composer-actions"><button type="button" className="primary" onClick={props.onSend} disabled={props.busy || !request.query.trim()}>{copy.send}</button><button type="button" className="secondary-command" onClick={props.onCancel} disabled={!props.busy}>{copy.cancel}</button><button type="button" className="secondary-command" onClick={props.onDoubleFire} disabled={props.busy}>{copy.doubleFire}</button></div>
  </section>;
}
