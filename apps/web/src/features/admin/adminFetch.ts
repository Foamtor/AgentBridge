import { apiBase } from "../../lib/apiBase";
import { getToken } from "../auth/token";

export function adminErrorMessage(error: unknown, locale: "zh-CN" | "en" = "zh-CN"): string {
  const status = (error as { status?: number } | null)?.status;
  const messages = locale === "en"
    ? { 401: "Your session has expired. Sign in again.", 403: "Your account is not allowed to perform this action.", 409: "This conflicts with the current configuration. Refresh and try again.", 422: "The submitted values are invalid. Check them and try again.", 429: "Too many requests. Try again shortly.", 503: "The service is temporarily unavailable. Check its configuration." }
    : { 401: "登录状态已失效，请重新登录。", 403: "当前账号没有执行此操作的权限。", 409: "当前操作与已有配置冲突，请刷新后重试。", 422: "提交内容不符合要求，请检查后重试。", 429: "请求过于频繁，请稍后重试。", 503: "服务暂不可用，请检查相关配置。" };
  if (status && status in messages) return messages[status as keyof typeof messages];
  return error instanceof Error ? error.message : "Request failed";
}

export type AdminRequestError = Error & {
  status?: number;
  code?: string;
  reason?: string;
  field?: string;
  validationType?: string;
};

export async function adminFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = getToken().trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase()}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as {
      detail?: { code?: string; reason?: string } | string | Array<{ loc?: unknown; type?: unknown }>;
    };
    const detail = !Array.isArray(body.detail) && typeof body.detail === "object" && body.detail ? body.detail : {};
    const locale = window.localStorage.getItem("agentbridge_locale") === "en" ? "en" : "zh-CN";
    const message = adminErrorMessage({ status: res.status }, locale);
    const error = new Error(message) as AdminRequestError;
    error.status = res.status;
    error.code = typeof detail.code === "string" ? detail.code : undefined;
    error.reason = typeof detail.reason === "string" ? detail.reason : undefined;
    if (Array.isArray(body.detail)) {
      const validation = body.detail.find((item) => item && typeof item === "object");
      const loc = Array.isArray(validation?.loc) ? validation.loc : [];
      const field = loc.at(-1);
      error.field = typeof field === "string" && field !== "body" ? field : undefined;
      error.validationType = typeof validation?.type === "string" ? validation.type : undefined;
    }
    if (
      (res.status === 401 && error.code !== "current_password_required" && error.code !== "reauth_invalid_credentials")
      || (res.status === 403 && error.code === "forbidden")
    ) {
      window.dispatchEvent(new CustomEvent("agentbridge:auth-error", { detail: { status: res.status } }));
    }
    throw error;
  }
  return (await res.json()) as T;
}
