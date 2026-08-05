import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiBase } from "../../lib/apiBase";

export type Session = {
  status: "anonymous" | "password_change_required" | "authenticated";
  username?: string;
  permissions?: string[];
};

type AuthContextValue = {
  session: Session | null;
  refresh: () => Promise<Session>;
  login: (username: string, password: string) => Promise<Session>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<Session>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function requestSession(path: string, init?: RequestInit): Promise<Session> {
  const response = await fetch(`${apiBase()}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(new Error(body?.detail?.code ?? `HTTP ${response.status}`), { status: response.status });
  }
  return (await response.json()) as Session;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const refresh = async () => {
    const next = await requestSession("/auth/session");
    setSession(next);
    return next;
  };
  useEffect(() => { void refresh().catch(() => setSession({ status: "anonymous" })); }, []);
  const value = useMemo<AuthContextValue>(() => ({
    session,
    refresh,
    login: async (username, password) => {
      const next = await requestSession("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      setSession(next); return next;
    },
    changePassword: async (currentPassword, newPassword) => {
      const next = await requestSession("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
      setSession(next); return next;
    },
    logout: async () => {
      await fetch(`${apiBase()}/auth/logout`, { method: "POST", credentials: "include" });
      setSession({ status: "anonymous" });
    },
  }), [session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
