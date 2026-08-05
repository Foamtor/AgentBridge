import type { PlaygroundCopy } from "./copy";
import type { ChatRequest } from "./types";

type RouteOption = { name: string; description: string };

type Props = {
  copy: PlaygroundCopy;
  request: ChatRequest;
  extraText: string;
  routes: RouteOption[];
  busy: boolean;
  error: string | null;
  copied: boolean;
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
  return <section className="composer-zone">
    <div className="section-title"><h2>{copy.request}</h2><div className="quiet-actions">
      <button type="button" className="text-command" onClick={props.onNewThread}>{copy.newThread}</button>
      <button type="button" className="text-command" onClick={props.onLoad} disabled={!props.canLoad}>{copy.replay}</button>
      <button type="button" className="text-command" onClick={props.onCopyCurl}>{props.copied ? copy.copied : copy.copyCurl}</button>
    </div></div>
    <div className="request-fields">
      <label><span>{copy.route}</span><select value={request.route} onChange={(event) => patch({ route: event.target.value })}>
        {props.routes.map((route) => <option value={route.name} key={route.name}>{route.description ? `${route.name} - ${route.description}` : route.name}</option>)}
        {!props.routes.some((route) => route.name === request.route) ? <option value={request.route}>{request.route}</option> : null}
      </select></label>
      <label><span>{copy.thread}</span><input value={request.thread_id} onChange={(event) => patch({ thread_id: event.target.value })} /></label>
      <label><span>{copy.model}</span><input value={request.model} onChange={(event) => patch({ model: event.target.value })} /></label>
    </div>
    <label className="query-field"><span>{copy.query}</span><textarea rows={4} value={request.query} onChange={(event) => patch({ query: event.target.value })} /></label>
    <details className="request-advanced"><summary>{copy.advanced}</summary><label><span>{copy.extra}</span><textarea className="json-editor" rows={6} spellCheck={false} value={props.extraText} onChange={(event) => props.onExtraText(event.target.value)} /></label></details>
    {props.error ? <p className="composer-error" role="alert">{props.error}</p> : null}
    <div className="composer-actions"><button type="button" className="primary" onClick={props.onSend} disabled={props.busy || !request.query.trim()}>{copy.send}</button><button type="button" className="secondary-command" onClick={props.onCancel} disabled={!props.busy}>{copy.cancel}</button><button type="button" className="secondary-command" onClick={props.onDoubleFire} disabled={props.busy}>{copy.doubleFire}</button></div>
  </section>;
}
