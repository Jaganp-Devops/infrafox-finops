function Card({ label, value, sublabel, color }) {
  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "16px 20px",
        flex: 1,
        backgroundColor: "#fff",
      }}
    >
      <p style={{ margin: 0, fontSize: "0.85rem", color: "#666" }}>{label}</p>
      <p style={{ margin: "4px 0 0 0", fontSize: "1.8rem", fontWeight: 700, color: color || "#111" }}>
        {value}
      </p>
      {sublabel && <p style={{ margin: "4px 0 0 0", fontSize: "0.8rem", color: "#999" }}>{sublabel}</p>}
    </div>
  );
}

export default function SummaryCards({ findings, costSummary }) {
  const findingsBySeverity = { high: 0, medium: 0, low: 0 };
  let totalSavings = 0;

  for (const f of findings || []) {
    if (findingsBySeverity[f.severity] !== undefined) {
      findingsBySeverity[f.severity] += 1;
    }
    if (f.estimated_monthly_savings_usd) {
      totalSavings += f.estimated_monthly_savings_usd;
    }
  }

  return (
    <div style={{ display: "flex", gap: "16px", marginBottom: "24px" }}>
      <Card
        label="Total Spend (30d)"
        value={costSummary ? `$${costSummary.total_usd.toFixed(2)}` : "-"}
      />
      <Card
        label="Open Findings"
        value={findings ? findings.length : "-"}
        sublabel={`${findingsBySeverity.high} high, ${findingsBySeverity.medium} medium, ${findingsBySeverity.low} low`}
      />
      <Card
        label="Potential Monthly Savings"
        value={`$${totalSavings.toFixed(2)}`}
        color="#2e7d32"
        sublabel="Estimated, not guaranteed"
      />
    </div>
  );
}
