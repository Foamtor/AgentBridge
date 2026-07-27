import { Link, useLocation } from "react-router-dom";

export function ForbiddenPage() {
  const location = useLocation();
  const message =
    (location.state as { message?: string } | null)?.message ??
    "当前账号缺少管理权限。";

  return (
    <main className="page">
      <h1>无权限</h1>
      <p className="error">{message}</p>
      <p>
        <Link to="/">返回总览</Link>
      </p>
    </main>
  );
}
