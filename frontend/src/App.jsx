import { useState, useEffect } from "react";
import { api } from "./api/client";
import SummaryCards from "./components/SummaryCards";
import FindingsList from "./components/FindingsList";

export default function App() {
  const [findings, setFindings] = useState(null);
  const [costSummary, setCostSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [lastScan, setLastScan] = useState(null);
  const [usageHours, setUsageHours] = useState(null);

  async function loadLatest() {
    setLoading(true);
    setError(null);
    try {
	const [scanData, costData, usageData] = await Promise.all([
	  api.getLatestFindings(),
	  api.getCostSummary(30),
	  api.getEc2UsageHours(30),
	]);
	setFindings(scanData.findings);
	setLastScan(scanData);
	setCostSummary(costData);
	setUsageHours(usageData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function runNewScan() {
    setLoading(true);
    setError(null);
    try {
      const scanData = await api.getFindings();
      setFindings(scanData.findings);
      setLastScan(scanData);
      const costData = await api.getCostSummary(30);
      setCostSummary(costData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLatest();
  }, []);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: "1000px", margin: "0 auto", padding: "24px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h1 style={{ margin: 0 }}>InfraFox</h1>
          <p style={{ margin: "4px 0 0 0", color: "#666" }}>AWS FinOps & Cloud Cost Optimization Platform</p>
        </div>
        <button
          onClick={runNewScan}
          disabled={loading}
          style={{
            padding: "10px 20px",
            fontSize: "0.95rem",
            fontWeight: 600,
            backgroundColor: loading ? "#ccc" : "#1976d2",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: loading ? "default" : "pointer",
          }}
        >
          {loading ? "Scanning..." : "Run New Scan"}
        </button>
      </header>

      {error && (
        <div style={{ backgroundColor: "#ffebee", color: "#c62828", padding: "12px 16px", borderRadius: "6px", marginBottom: "16px" }}>
          Error: {error}
        </div>
      )}

      {lastScan && (
        <p style={{ fontSize: "0.85rem", color: "#999", marginBottom: "16px" }}>
          Last scan: {lastScan.scan_id} — {lastScan.resources_scanned} resources scanned,{" "}
          {lastScan.duration_seconds}s
          {lastScan.failed_checks && lastScan.failed_checks.length > 0 && (
            <span style={{ color: "#c62828" }}> ({lastScan.failed_checks.length} checks failed)</span>
          )}
        </p>
      )}

      <SummaryCards findings={findings} costSummary={costSummary} />

      <h2 style={{ fontSize: "1.1rem", marginBottom: "12px" }}>Findings</h2>
      <FindingsList findings={findings} onSelect={setSelected} />

      {selected && (
        <div
          onClick={() => setSelected(null)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: "white",
              borderRadius: "8px",
              padding: "24px",
              maxWidth: "600px",
              width: "90%",
              maxHeight: "80vh",
              overflowY: "auto",
            }}
          >
            <h3 style={{ marginTop: 0 }}>{selected.rule_id} — {selected.resource_id}</h3>
            <p><strong>Condition:</strong> {selected.condition_description}</p>
            <p><strong>Recommendation:</strong> {selected.recommendation}</p>
            <p><strong>Evidence:</strong></p>
            <pre style={{ backgroundColor: "#f5f5f5", padding: "12px", borderRadius: "6px", overflowX: "auto", fontSize: "0.85rem" }}>
              {JSON.stringify(selected.evidence, null, 2)}
            </pre>
            <button onClick={() => setSelected(null)} style={{ marginTop: "8px" }}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
