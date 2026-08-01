/**
 * Client-side navigation hint only. The API remains the authorization boundary.
 * A missing token keeps the local development console usable.
 */
export function hasConsoleAdminAccess(token: string): boolean {
  if (!token.trim()) return true;
  const payload = token.split(".")[1];
  if (!payload) return false;
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(atob(normalized)) as {
      roles?: unknown;
      permissions?: unknown;
    };
    const roles = Array.isArray(claims.roles) ? claims.roles : [];
    const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
    return (
      roles.includes("admin") ||
      permissions.includes("*") ||
      permissions.includes("admin:*") ||
      permissions.includes("admin:read")
    );
  } catch {
    return false;
  }
}
