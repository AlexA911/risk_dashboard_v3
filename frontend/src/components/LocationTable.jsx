/**
 * LocationTable.jsx
 * Simple office-level VaR + Margin table. No drill-down.
 * Drill-down is handled by LocationTable_New.jsx on the Summary - New tab.
 */
import React, { useEffect, useState } from "react";
import { getLocationTable } from "../api/client";

function fmtNum(val) {
  if (val === null || val === undefined) return "—";
  return Math.round(Math.abs(val)).toLocaleString("en-GB");
}

function DeltaCell({ val }) {
  if (val === null || val === undefined) return <td style={s.td}>—</td>;
  const up = val >= 0;
  return (
    <td style={{ ...s.td, color: up ? "#ef4444" : "#22c55e", fontWeight: 500 }}>
      {up ? "▲" : "▼"} {Math.abs(Math.round(val)).toLocaleString("en-GB")}
    </td>
  );
}

function TableHeader() {
  return (
    <thead>
      <tr>
        <th style={{ ...s.th, textAlign: "left" }}>Location</th>
        <th style={s.th}>VaR 10D</th>
        <th style={s.th}>Δ SOD</th>
        <th style={s.th}>VaR 100D</th>
        <th style={s.th}>Δ SOD</th>
        <th style={s.th}>Init. Margin</th>
        <th style={s.th}>Δ SOD</th>
      </tr>
    </thead>
  );
}

export default function LocationTable({ location }) {
  const [locData,    setLocData]    = useState([]);
  const [locLoading, setLocLoading] = useState(true);
  const [locError,   setLocError]   = useState(null);

  useEffect(() => {
    setLocLoading(true);
    setLocError(null);
    getLocationTable(location)
      .then(r => { setLocData(r.data.data); setLocLoading(false); })
      .catch(e => { setLocError(e.message); setLocLoading(false); });
  }, [location]);

  if (locLoading) return <div style={s.msg}>Loading...</div>;
  if (locError)   return <div style={s.err}>Error: {locError}</div>;

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span style={s.title}>Portfolio / Office</span>
        <span style={s.sub}>Values in USD</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={s.table}>
          <TableHeader />
          <tbody>
            {locData.map((row, i) => {
              const isFF = row.Office === "Futures First";
              return (
                <tr
                  key={row.Office}
                  style={{
                    background:   i % 2 === 0 ? "#fff" : "#f8fafc",
                    borderBottom: "1px solid #f1f5f9",
                    borderLeft:   "3px solid transparent",
                    fontWeight:   isFF ? 700 : 400,
                  }}
                >
                  <td style={{ ...s.td, textAlign: "left", fontWeight: isFF ? 700 : 600, color: "#0f172a" }}>
                    {row.Office}
                  </td>
                  <td style={s.td}>{fmtNum(row.VaR_10D)}</td>
                  <DeltaCell val={row.Delta_10D} />
                  <td style={s.td}>{fmtNum(row.VaR_100D)}</td>
                  <DeltaCell val={row.Delta_100D} />
                  <td style={s.td}>{fmtNum(row.Margin)}</td>
                  <DeltaCell val={row.Delta_Margin} />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const s = {
  wrap:  { background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" },
  header:{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 },
  title: { fontSize: 14, fontWeight: 700, color: "#0f172a" },
  sub:   { fontSize: 11, color: "#94a3b8" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:    { background: "#f8fafc", padding: "8px 12px", textAlign: "right", fontWeight: 600, fontSize: 11, color: "#64748b", borderBottom: "2px solid #e2e8f0", whiteSpace: "nowrap" },
  td:    { padding: "7px 12px", textAlign: "right", whiteSpace: "nowrap" },
  msg:   { padding: 20, color: "#94a3b8", fontSize: 12 },
  err:   { padding: 16, color: "#ef4444", fontSize: 12 },
};
