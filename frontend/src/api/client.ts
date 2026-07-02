// Dev traffic goes through the Vite proxy (/api -> http://localhost:8000).
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export interface HealthOut {
  status: string;
  version: string;
}

export async function getHealth(): Promise<HealthOut> {
  const resp = await fetch(`${API_BASE}/health`);
  if (!resp.ok) throw new Error(`health check failed: ${resp.status}`);
  return resp.json();
}
