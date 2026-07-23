import { Link } from "react-router-dom";
import { AppRoutes } from "./routes";

export function App() {
  return (
    <div className="shell">
      <nav className="nav">
        <strong>Agent-Base</strong>
        <Link to="/">调试</Link>
        <Link to="/contracts">契约</Link>
      </nav>
      <AppRoutes />
    </div>
  );
}
