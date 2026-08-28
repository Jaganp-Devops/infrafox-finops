const SEVERITY_COLORS = {
  high: "#d32f2f",
  medium: "#f57c00",
  low: "#757575",
};

function SeverityBadge({ severity }) {
  return (
    <span
      style={{
        backgroundColor: SEVERITY_COLORS[severity] || "#757575",
        color: "white",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "0.75rem",
        fontWeight: 600,
        textTransform: "uppercase",
      }}
    >
      {severity}
    </span>
  );
}

function ConfidenceBadge({ confidence }) {
  return (
    <span style={{ fontSize: "0.75rem", color: "#666" }}>
      confidence: {confidence}
    </span>
  );
}

export default function FindingsList({ findings, onSelect }) {
  if (!findings || findings.length === 0) {
    return <p style={{ color: "#666" }}>No findings. Run a scan to check for cost issues.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {findings.map((f) => (
        <div
          key={`${f.rule_id}-${f.resource_id}`}
          onClick={() => onSelect && onSelect(f)}
          style={{
            border: "1px solid #ddd",
            borderRadius: "6px",
            padding: "12px 16px",
            cursor: onSelect ? "pointer" : "default",
            backgroundColor: "#fff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>{f.rule_id}</strong>
              <span style={{ marginLeft: "8px", color: "#666" }}>{f.resource_type}</span>
              <span style={{ marginLeft: "8px", fontFamily: "monospace", fontSize: "0.85rem" }}>
                {f.resource_id}
              </span>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <SeverityBadge severity={f.severity} />
              <ConfidenceBadge confidence={f.confidence} />
            </div>
          </div>
          <p style={{ margin: "8px 0 4px 0" }}>{f.condition_description}</p>
          <p style={{ margin: "4px 0", color: "#333" }}>{f.recommendation}</p>
          {f.estimated_monthly_savings_usd != null && (
            <p style={{ margin: "4px 0", color: "#2e7d32", fontWeight: 600 }}>
              Estimated savings: ${f.estimated_monthly_savings_usd.toFixed(2)}/month
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
