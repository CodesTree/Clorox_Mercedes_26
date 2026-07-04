import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

async function enableMocks() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MSW === "true") {
    const { worker } = await import("./api/browser");
    await worker.start({ onUnhandledRequest: "bypass" });
  }
}

enableMocks().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
