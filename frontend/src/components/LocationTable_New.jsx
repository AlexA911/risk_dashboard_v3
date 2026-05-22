/**
 * LocationTable_New.jsx
 * Level 1: Office rows — click to show sector breakdown + update chart
 * Level 2: Sector rows — click to expand products + update chart to sector iVaR
 * Level 3: Subgroup separator rows + product rows — click to update chart to product iVaR
 */
import React, { useEffect, useState } from "react";
import { getLocationTable, getAssetClassTableGrouped, getProductTableBySector } from "../api/client";

async function fetchSectorTable(location) {
  const r = await getAssetClassTableGrouped(location);
  return r.data.data;
}

async function fetchProductsBySector(location, sector) {
  const r = await getProductTableBySector(location, sector);
  return r.data.data;
}

const SECTOR_COLOURS = {
  "Energy":     "#f97316",
  "Rates":      "#3b82f6",
  "Equities":   "#ec4899",
  "Volatility": "#8b5cf6",
  "FX":         "#10b981",
  "Softs":      "#eab308",
  "Ags":        "#84cc16",
  "Metals":     "#64748b",
  "Crypto":     "#06b6d4",
};

function officeDisplayName(office) {
  if (office === "Futures First") return "Futures First — Total";
  return office;
}

function fmtNum(val) {
  if (val === null || val === undefined) return "—";
  return Math.round(Math.abs(val)).toLocaleString("en-GB");
}

function DeltaCell({ val, style = {} }) {
  if (val === null || val === undefined) return <td style={{ ...s.td, ...style }}>—</td>;
  const up = val >= 0;
  return (
    <td style={{ ...s.td, color: up ? "#ef4444" : "#22c55e", fontWeight: 500, ...style }}>
      {up ? "▲" : "▼"} {Math.abs(Math.round(val)).toLocaleString("en-GB")}
    </td>
  );
}

function GroupHeader({ label }) {
  return (
    <th colSpan={3} style={{
      ...s.th, textAlign: "center", borderBottom: "1px solid #e2e8f0",
      borderLeft: "1px solid #e2e8f0", color: "#475569", fontSize: 10,
      letterSpacing: "0.05em", textTransform: "uppercase", paddingBottom: 4,
    }}>
      {label}
    </th>
  );
}

export default function LocationTable_New({ location, refreshKey, onOfficeClick, onSectorClick, onProductClick }) {
  const [locData,    setLocData]    = useState([]);
  const [locLoading, setLocLoading] = useState(true);
  const [locError,   setLocError]   = useState(null);

  const [selectedOffice, setSelectedOffice] = useState(null);
  const [sectorData,     setSectorData]     = useState([]);
  const [sectorLoading,  setSectorLoading]  = useState(false);
  const [sectorError,    setSectorError]    = useState(null);
  const [sectorApiLoc,   setSectorApiLoc]   = useState(null);

  const [productState,   setProductState]   = useState({});
  const [expandedSector, setExpandedSector] = useState(null);
  const [varMode,        setVarMode]        = useState("100D");

  useEffect(() => {
    setLocLoading(true);
    setLocError(null);
    setSelectedOffice(null);
    setSectorData([]);
    setExpandedSector(null);
    setProductState({});
    getLocationTable(location)
      .then(r => { setLocData(r.data.data); setLocLoading(false); })
      .catch(e => { setLocError(e.message); setLocLoading(false); });
  }, [location, refreshKey]);

  function handleOfficeClick(office) {
    if (onOfficeClick) onOfficeClick(office);
    if (selectedOffice === office) {
      setSelectedOffice(null);
      setSectorData([]);
      setExpandedSector(null);
      setProductState({});
      return;
    }
    setSelectedOffice(office);
    setSectorData([]);
    setSectorLoading(true);
    setSectorError(null);
    setExpandedSector(null);
    setProductState({});
    const apiLoc = office === "Futures First" ? "Total" : office;
    setSectorApiLoc(apiLoc);
    fetchSectorTable(apiLoc)
      .then(data => { setSectorData(data); setSectorLoading(false); })
      .catch(e   => { setSectorError(e.message); setSectorLoading(false); });
  }

  function handleSectorClick(sector) {
    if (onSectorClick) onSectorClick(sector, selectedOffice);
    if (expandedSector === sector) {
      setExpandedSector(null);
      return;
    }
    setExpandedSector(sector);
    if (productState[sector]?.data) return;
    setProductState(prev => ({ ...prev, [sector]: { loading: true, error: null, data: null } }));
    fetchProductsBySector(sectorApiLoc, sector)
      .then(data => setProductState(prev => ({ ...prev, [sector]: { loading: false, error: null, data } })))
      .catch(e   => setProductState(prev => ({ ...prev, [sector]: { loading: false, error: e.message, data: null } })));
  }

  function handleProductClick(product) {
    if (onProductClick) onProductClick(product, selectedOffice);
  }

  if (locLoading) return <div style={s.msg}>Loading...</div>;
  if (locError)   return <div style={s.err}>Error: {locError}</div>;

  function VarToggle() {
    return (
      <div style={{ display: "inline-flex", alignItems: "center", background: "#e2e8f0", borderRadius: 6, padding: 2, gap: 2 }}>
        {["100D", "10D"].map(mode => (
          <button
            key={mode}
            onClick={e => { e.stopPropagation(); setVarMode(mode); }}
            style={{
              padding: "2px 10px", borderRadius: 4, border: "none", cursor: "pointer",
              fontSize: 10, fontWeight: 700, letterSpacing: "0.04em",
              background: varMode === mode ? "#fff" : "transparent",
              color:      varMode === mode ? "#0f172a" : "#94a3b8",
              boxShadow:  varMode === mode ? "0 1px 2px rgba(0,0,0,0.10)" : "none",
              transition: "all 0.15s",
            }}
          >
            {mode}
          </button>
        ))}
      </div>
    );
  }

  function TableHead() {
    return (
      <thead>
        <tr>
          <th style={{ ...s.th, textAlign: "left", borderBottom: "1px solid #e2e8f0" }} rowSpan={2}>
            Location
          </th>
          {/* VAR toggle header — spans 3 cols */}
          <th colSpan={3} style={{
            ...s.th, textAlign: "center", borderBottom: "1px solid #e2e8f0",
            borderLeft: "1px solid #e2e8f0", padding: "4px 10px",
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
              <span style={{ fontSize: 10, color: "#475569", letterSpacing: "0.05em", textTransform: "uppercase" }}>VaR</span>
              <VarToggle />
            </div>
          </th>
          {/* P&L placeholder headers */}
          <th style={{
            ...s.th, textAlign: "center", borderBottom: "1px solid #e2e8f0",
            borderLeft: "1px solid #e2e8f0", color: "#94a3b8", fontSize: 10,
            letterSpacing: "0.05em", textTransform: "uppercase",
          }}>
            1D P&L
          </th>
          <th style={{
            ...s.th, textAlign: "center", borderBottom: "1px solid #e2e8f0",
            color: "#94a3b8", fontSize: 10,
            letterSpacing: "0.05em", textTransform: "uppercase",
          }}>
            5D P&L
          </th>
          <GroupHeader label="Init. Margin" />
        </tr>
        <tr>
          <th style={{ ...s.th, borderLeft: "1px solid #e2e8f0" }}>Current</th>
          <th style={s.th}>Δ SOD</th>
          <th style={s.th}>Δ t-1</th>
          <th style={{ ...s.th, borderLeft: "1px solid #e2e8f0", color: "#cbd5e1" }}>coming soon</th>
          <th style={{ ...s.th, color: "#cbd5e1" }}>coming soon</th>
          <th style={{ ...s.th, borderLeft: "1px solid #e2e8f0" }}>Current</th>
          <th style={s.th}>Δ SOD</th>
          <th style={s.th}>Δ t-1</th>
        </tr>
      </thead>
    );
  }

  function OfficeRow({ row, i }) {
    const isFF       = row.Office === "Futures First";
    const isSelected = selectedOffice === row.Office;
    const varCurrent = varMode === "100D" ? row.VaR_100D  : row.VaR_10D;
    const varDelta   = varMode === "100D" ? row.Delta_100D : row.Delta_10D;
    const varDeltaT1 = varMode === "100D" ? row.Delta_100D_t1 : row.Delta_10D_t1;
    return (
      <tr
        onClick={() => handleOfficeClick(row.Office)}
        style={{
          background:   isSelected ? "#eff6ff" : isFF ? "#f8fafc" : i % 2 === 0 ? "#fff" : "#fafafa",
          borderBottom: isFF ? "2px solid #e2e8f0" : "1px solid #f1f5f9",
          borderLeft:   isSelected ? "3px solid #3b82f6" : "3px solid transparent",
          cursor:       "pointer",
          fontWeight:   isFF ? 700 : 400,
          transition:   "background 0.15s",
        }}
      >
        <td style={{ ...s.td, textAlign: "left" }}>{officeDisplayName(row.Office)}</td>
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(varCurrent)}</td>
        <DeltaCell val={varDelta} />
        <DeltaCell val={varDeltaT1} />
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9", color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>—</td>
        <td style={{ ...s.td, color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>—</td>
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(row.Margin)}</td>
        <DeltaCell val={row.Delta_Margin} />
        <DeltaCell val={row.Delta_Margin_t1} />
      </tr>
    );
  }

  function SectorRow({ row, i, colour, isExpanded }) {
    const varCurrent = varMode === "100D" ? row.VaR_100D  : row.VaR_10D;
    const varDelta   = varMode === "100D" ? row.Delta_100D : row.Delta_10D;
    const varDeltaT1 = varMode === "100D" ? row.Delta_100D_t1 : row.Delta_10D_t1;
    return (
      <tr
        onClick={() => handleSectorClick(row.Sector)}
        style={{
          background:   isExpanded ? `${colour}10` : i % 2 === 0 ? "#fff" : "#fafafa",
          borderBottom: "1px solid #f1f5f9",
          borderLeft:   `3px solid ${colour}`,
          cursor:       "pointer",
          transition:   "background 0.15s",
        }}>
        <td style={{ ...s.td, textAlign: "left", fontWeight: 600, color: "#0f172a" }}>
          <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: colour, marginRight: 8 }} />
          {row.Sector}
          <span style={{ marginLeft: 6, fontSize: 10, color: "#94a3b8" }}>{isExpanded ? "▲" : "▼"}</span>
        </td>
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(varCurrent)}</td>
        <DeltaCell val={varDelta} />
        <DeltaCell val={varDeltaT1} />
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9", color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>—</td>
        <td style={{ ...s.td, color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>—</td>
        <td style={{ ...s.td, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(row.Margin)}</td>
        <DeltaCell val={row.Delta_Margin} />
        <DeltaCell val={row.Delta_Margin_t1} />
      </tr>
    );
  }

  function SubgroupHeaderRow({ label, colour }) {
    return (
      <tr style={{ background: "#f8fafc", borderLeft: `3px solid ${colour}40` }}>
        <td colSpan={9} style={{
          ...s.td, textAlign: "left", paddingLeft: 24, paddingTop: 4, paddingBottom: 4,
          fontSize: 10, fontWeight: 700, color: colour, letterSpacing: "0.06em",
          textTransform: "uppercase", borderBottom: `1px solid ${colour}30`,
        }}>
          {label}
        </td>
      </tr>
    );
  }

  function ProductRow({ prod, pi, colour }) {
    const varCurrent = varMode === "100D" ? prod.VaR_100D  : prod.VaR_10D;
    const varDelta   = varMode === "100D" ? prod.Delta_100D : prod.Delta_10D;
    const varDeltaT1 = varMode === "100D" ? prod.Delta_100D_t1 : prod.Delta_10D_t1;
    return (
      <tr
        onClick={() => handleProductClick(prod.Product)}
        style={{
          background:   pi % 2 === 0 ? "#f8fafc" : "#f1f5f9",
          borderBottom: "1px solid #e9edf2",
          borderLeft:   `3px solid ${colour}40`,
          cursor:       "pointer",
          transition:   "background 0.15s",
        }}
      >
        <td style={{ ...s.td, textAlign: "left", paddingLeft: 36, color: "#334155", fontSize: 11 }}>
          <span style={{ color: colour, marginRight: 6 }}>└</span>
          {prod.Product}
          <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>{prod.Asset_Class}</span>
        </td>
        <td style={{ ...s.td, fontSize: 11, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(varCurrent)}</td>
        <DeltaCell val={varDelta}    style={{ fontSize: 11 }} />
        <DeltaCell val={varDeltaT1} style={{ fontSize: 11 }} />
        <td style={{ ...s.td, fontSize: 11, borderLeft: "1px solid #f1f5f9", color: "#cbd5e1", fontStyle: "italic" }}>—</td>
        <td style={{ ...s.td, fontSize: 11, color: "#cbd5e1", fontStyle: "italic" }}>—</td>
        <td style={{ ...s.td, fontSize: 11, borderLeft: "1px solid #f1f5f9" }}>{fmtNum(prod.Margin)}</td>
        <DeltaCell val={prod.Delta_Margin}    style={{ fontSize: 11 }} />
        <DeltaCell val={prod.Delta_Margin_t1} style={{ fontSize: 11 }} />
      </tr>
    );
  }

  function renderProducts(products, colour) {
    if (!products || products.length === 0) return null;
    const hasSubgroups = products.some(p => p.Subgroup && p.Subgroup !== "Other");
    if (!hasSubgroups) {
      return products.map((prod, pi) => (
        <ProductRow key={prod.Product} prod={prod} pi={pi} colour={colour} />
      ));
    }
    const groups = [];
    let currentGroup = null;
    products.forEach(prod => {
      const sg = prod.Subgroup || "Other";
      if (sg !== currentGroup) {
        currentGroup = sg;
        groups.push({ label: sg, items: [] });
      }
      groups[groups.length - 1].items.push(prod);
    });
    let pi = 0;
    return groups.map(group => (
      <React.Fragment key={group.label}>
        <SubgroupHeaderRow label={group.label} colour={colour} />
        {group.items.map(prod => {
          const row = <ProductRow key={prod.Product} prod={prod} pi={pi} colour={colour} />;
          pi++;
          return row;
        })}
      </React.Fragment>
    ));
  }

  return (
    <div>
      {/* ── Level 1: Office table ── */}
      <div style={s.wrap}>
        <div style={s.header}>
          <span style={s.title}>Portfolio / Office</span>
          <span style={s.sub}>Values in USD</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={s.table}>
            <TableHead />
            <tbody>
              {locData.map((row, i) => (
                <OfficeRow key={row.Office} row={row} i={i} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Level 2: Sector breakdown panel ── */}
      {selectedOffice && (
        <div style={{ ...s.wrap, marginTop: 12 }}>
          <div style={s.header}>
            <span style={s.title}>
              Sector Breakdown
              <span style={{ fontWeight: 400, color: "#64748b", marginLeft: 8 }}>
                · {officeDisplayName(selectedOffice)}
              </span>
            </span>
            <span
              style={{ ...s.sub, cursor: "pointer", color: "#3b82f6" }}
              onClick={() => {
                setSelectedOffice(null);
                setSectorData([]);
                setExpandedSector(null);
                setProductState({});
                if (onOfficeClick) onOfficeClick("Futures First");
              }}
            >
              ✕ Close
            </span>
          </div>

          {sectorLoading && <div style={s.msg}>Loading...</div>}
          {sectorError   && <div style={s.err}>Error: {sectorError}</div>}
          {!sectorLoading && !sectorError && sectorData.length === 0 && (
            <div style={s.msg}>No sector data available yet.</div>
          )}

          {!sectorLoading && !sectorError && sectorData.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table style={s.table}>
                <TableHead />
                <tbody>
                  {sectorData.map((row, i) => {
                    const colour     = SECTOR_COLOURS[row.Sector] ?? "#94a3b8";
                    const isExpanded = expandedSector === row.Sector;
                    const ps         = productState[row.Sector];
                    return (
                      <React.Fragment key={row.Sector}>
                        <SectorRow row={row} i={i} colour={colour} isExpanded={isExpanded} />
                        {isExpanded && (
                          <>
                            {ps?.loading && (
                              <tr><td colSpan={9} style={{ ...s.td, textAlign: "left", color: "#94a3b8", paddingLeft: 40 }}>Loading products...</td></tr>
                            )}
                            {ps?.error && (
                              <tr><td colSpan={9} style={{ ...s.td, textAlign: "left", color: "#ef4444", paddingLeft: 40 }}>Error: {ps.error}</td></tr>
                            )}
                            {ps?.data && ps.data.length === 0 && (
                              <tr><td colSpan={9} style={{ ...s.td, textAlign: "left", color: "#94a3b8", paddingLeft: 40 }}>No product data available.</td></tr>
                            )}
                            {ps?.data && renderProducts(ps.data, colour)}
                            <tr style={{ borderLeft: `3px solid ${colour}` }}>
                              <td colSpan={9} style={{ padding: "2px 0", background: "#f8fafc", borderBottom: "2px solid #e2e8f0" }} />
                            </tr>
                          </>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const s = {
  wrap:  { background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" },
  header:{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 },
  title: { fontSize: 14, fontWeight: 700, color: "#0f172a" },
  sub:   { fontSize: 11, color: "#94a3b8" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th:    { background: "#f8fafc", padding: "6px 10px", textAlign: "right", fontWeight: 600, fontSize: 11, color: "#64748b", borderBottom: "2px solid #e2e8f0", whiteSpace: "nowrap" },
  td:    { padding: "7px 10px", textAlign: "right", whiteSpace: "nowrap" },
  msg:   { padding: 20, color: "#94a3b8", fontSize: 12 },
  err:   { padding: 16, color: "#ef4444", fontSize: 12 },
};
