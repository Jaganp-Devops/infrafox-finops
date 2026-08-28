// Central API client. Every request goes through here so the backend
// base URL only needs to change in one place - currently pointed at the
// EC2 instance directly on port 8000; Phase 5 will switch this to a
// relative path once Nginx reverse-proxies /api/ to the backend.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://3.109.152.62:8000";

async function request(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  getFindings: () => request("/api/v1/findings"),
  getLatestFindings: () => request("/api/v1/findings/latest"),
  getOpenFindings: () => request("/api/v1/findings/open"),
  getScanHistory: (limit = 20) => request(`/api/v1/scans?limit=${limit}`),
  getResourceHistory: (resourceId) => request(`/api/v1/resources/${resourceId}/history`),
  getCostSummary: (days = 30) => request(`/api/v1/costs/summary?days=${days}`),
  getInstances: () => request("/api/v1/resources/instances"),
};
