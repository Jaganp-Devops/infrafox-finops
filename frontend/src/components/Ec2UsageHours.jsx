export default function Ec2UsageHours({ usageData }) {
  const entries = usageData ? Object.entries(usageData) : [];

  if (entries.length === 0) {
    return null;
  }

  return (
    <div style={{ marginBottom: "24px" }}>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "12px" }}>Real EC2 Billed Hours (by instance type)</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {entries.map(([instanceType, data]) => (
          <div
            key={instanceType}
            style={{
              border: "1px solid #ddd",
              borderRadius: "6px",
              padding: "12px 16px",
              backgroundColor: "#fff",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span style={{ fontFamily: "monospace", fontWeight: 600 }}>{instanceType}</span>
            <span style={{ color: "#666" }}>{data.billed_hours} hours billed</span>
            <span style={{ color: "#2e7d32", fontWeight: 600 }}>${data.real_cost_usd.toFixed(2)} real cost</span>
          </div>
        ))}
      </div>
      <p style={{ fontSize: "0.8rem", color: "#999", marginTop: "8px" }}>
        Real billed hours from AWS Cost Explorer, grouped by instance type - not an estimate.
      </p>
    </div>
  );
}
