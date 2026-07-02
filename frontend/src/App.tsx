import { useEffect, useState } from "react";
import { getHealth } from "./api/client";
import "./styles/theme.css";

type ApiStatus = "checking" | "online" | "offline";

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [version, setVersion] = useState("");

  useEffect(() => {
    getHealth()
      .then((h) => {
        setApiStatus("online");
        setVersion(h.version);
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <span className="wordmark">
          <span className="wordmark-spark">*</span> AssetIQ
          <span className="wordmark-sub">for Mercedes-Benz</span>
        </span>
        <span className={`api-pill api-pill--${apiStatus}`} data-testid="api-status">
          {apiStatus === "checking"
            ? "Connecting..."
            : apiStatus === "online"
              ? `API online - v${version}`
              : "API offline"}
        </span>
      </header>
      <section className="stage">
        <p className="stage-placeholder">3D stage - Phase 04</p>
      </section>
    </main>
  );
}
