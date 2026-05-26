/**
 * RollRiskTab.jsx
 * Roll Risk tab — Fixed Income (Rates) and Equities product breakdown.
 *
 * Each section has:
 *   - a section summary row (_rowType: "section")  — Cumulus netted total
 *   - subgroup header rows  (_rowType: "subgroup") — per currency/index group
 *   - product rows          (_rowType: "product")
 */
import React, { useEffect, useState, useMemo, useCallback } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
ModuleRegistry.registerModules([AllCommunityModule]);
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import { getRollRisk } from "../api/client";

// ─── Constants ────────────────────────────────────────────────────────────────

const SECTION_COLOURS = {
  "Fixed Income": "#3b82f6",
  "Equities":     "#ec4899",
};

const TOTAL_COLOUR = "#8b5cf6";

const GRID_VARS = {
  "--ag-header-background-color":  "#f8fafc",
  "--ag-odd-row-background-color": "#fff",
  "--ag-row-hover-color":          "#f0f7ff",
  "--ag-border-color":             "#e2e8f0",
  "--ag-header-foreground-color":  "#64748b",
  "--ag-font-size":                "11px",
  "--ag-cell-horizontal-padding":  "10px",
  "--ag-row-height":               "30px",
  "--ag-header-height":            "30px",
  "--ag-borders":                  "none",
  "--ag-row-border-style":         "solid",
  "--ag-row-border-width":         "1px",
  "--ag-row-border-color":         "#f1f5f9",
};

// ─── Formatters ───────────────────────────────────────────────────────────────

function fmtM(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `$${(Math.abs(val) / 1_000_000).toFixed(1)}M`;
}

function fmtK(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `$${Math.round(Math.abs(val) / 1000).toLocaleString("en-GB")}K`;
}

function fmtDeltaM(delta) {
  if (delta === null || delta === undefined || isNaN(delta)) return null;
  const up = delta >= 0;
  return {
    text: `${up ? "▲" : "▼"} $${Math.abs(delta / 1_000_000).toFixed(1)}M from SOD`,
    up,
  };
}

function fmtDeltaK(delta) {
  if (delta === null || delta === undefined || isNaN(delta)) return null;
  const up = delta >= 0;
  return {
    text: `${up ? "▲" : "▼"} $${Math.abs(Math.round(delta / 1000)).toLocaleString("en-GB")}K from SOD`,
    up,
  };
}

// ─── Derive top-bar metrics from sections data ────────────────────────────────
// Uses the section-level row (_rowType: "section") for the true Cumulus netted figure.

function deriveMetrics(sections) {
  const totals = { margin: 0, marginDelta: 0, var: 0, varDelta: 0 };
  const bySection = {};

  for (const sec of sections) {
    const sectionRow = sec.rows.find(r => r._rowType === "section");
    const secVar         = sectionRow?.VaR_100D    ?? 0;
    const secVarDelta    = sectionRow?.Delta_100D  ?? 0;
    const secMargin      = sectionRow?.Margin      ?? 0;
    const secMarginDelta = sectionRow?.Delta_Margin ?? 0;

    bySection[sec.section] = {
      margin: secMargin, marginDelta: secMarginDelta,
      var: secVar,       varDelta: secVarDelta,
    };
    totals.margin      += secMargin;
    totals.marginDelta += secMarginDelta;
    totals.var         += secVar;
    totals.varDelta    += secVarDelta;
  }

  return { totals, bySection };
}

// ─── Metric card ──────────────────────────────────────────────────────────────

function RollMetricCard({ label, value, change, colour }) {
  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 2,
        borderTop: `3px solid ${colour}`,
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        background: "#fff",
      }}
    >
      <CardContent sx={{ p: "12px 14px !important" }}>
        <Typography sx={{
          fontSize: 10, fontWeight: 600, color: "#64748b",
          textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.5,
        }}>
          {label}
        </Typography>
        <Typography sx={{ fontSize: 20, fontWeight: 700, color: "#0f172a", mb: 0.25 }}>
          {value}
        </Typography>
        {change ? (
          <Typography sx={{
            fontSize: 10, fontWeight: 500,
            color: change.up ? "#ef4444" : "#22c55e",
          }}>
            {change.text}
          </Typography>
        ) : (
          <Typography sx={{ fontSize: 10 }}>&nbsp;</Typography>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Metrics bar ─────────────────────────────────────────────────────────────

function RollMetricsBar({ sections }) {
  const { totals, bySection } = useMemo(() => deriveMetrics(sections), [sections]);
  const fi = bySection["Fixed Income"] ?? {};
  const eq = bySection["Equities"]     ?? {};

  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 1.5, mb: 2 }}>
      <RollMetricCard label="Total Roll Margin"    value={fmtM(totals.margin)} change={fmtDeltaM(totals.marginDelta)} colour={TOTAL_COLOUR} />
      <RollMetricCard label="FI Roll Margin"       value={fmtM(fi.margin)}     change={fmtDeltaM(fi.marginDelta)}     colour={SECTION_COLOURS["Fixed Income"]} />
      <RollMetricCard label="Equity Roll Margin"   value={fmtM(eq.margin)}     change={fmtDeltaM(eq.marginDelta)}     colour={SECTION_COLOURS["Equities"]} />
      <RollMetricCard label="Total Roll VaR 100D"  value={fmtK(totals.var)}    change={fmtDeltaK(totals.varDelta)}    colour={TOTAL_COLOUR} />
      <RollMetricCard label="FI Roll VaR 100D"     value={fmtK(fi.var)}        change={fmtDeltaK(fi.varDelta)}        colour={SECTION_COLOURS["Fixed Income"]} />
      <RollMetricCard label="Equity Roll VaR 100D" value={fmtK(eq.var)}        change={fmtDeltaK(eq.varDelta)}        colour={SECTION_COLOURS["Equities"]} />
    </Box>
  );
}

// ─── Cell renderers ───────────────────────────────────────────────────────────

function DeltaRenderer({ value, data }) {
  if (value === null || value === undefined || value === "")
    return <span style={{ color: "#94a3b8" }}>—</span>;
  const up   = value >= 0;
  const bold = data?._rowType === "subgroup" || data?._rowType === "section";
  return (
    <span style={{ color: up ? "#ef4444" : "#22c55e", fontWeight: bold ? 700 : 500, fontSize: 11 }}>
      {up ? "▲" : "▼"} {Math.abs(Math.round(value)).toLocaleString("en-GB")}
    </span>
  );
}

function NumRenderer({ value, data }) {
  if (value === null || value === undefined)
    return <span style={{ color: "#94a3b8" }}>—</span>;
  const isSection = data?._rowType === "section";
  const isSubgroup = data?._rowType === "subgroup";
  return (
    <span style={{
      fontWeight: (isSection || isSubgroup) ? 700 : 400,
      color: isSection ? "#0f172a" : isSubgroup ? "#1e293b" : "#334155",
      fontSize: isSection ? 12 : 11,
    }}>
      {Math.round(Math.abs(value)).toLocaleString("en-GB")}
    </span>
  );
}

function ProductNameRenderer({ value, data }) {
  const colour = data?._sectionColour ?? "#94a3b8";

  if (data?._rowType === "section") {
    // Full-width summary row — bold, larger, section colour
    return (
      <span style={{
        color: colour,
        fontWeight: 800,
        fontSize: 12,
        letterSpacing: "0.04em",
        paddingLeft: 4,
      }}>
        {value}
      </span>
    );
  }

  if (data?._rowType === "subgroup") {
    return (
      <span style={{
        color: colour, fontWeight: 700, fontSize: 10,
        letterSpacing: "0.06em", textTransform: "uppercase",
        paddingLeft: 8,
      }}>
        {value}
      </span>
    );
  }

  return (
    <Box sx={{ pl: 3 }}>
      <span style={{ color: colour, marginRight: 6 }}>└</span>
      <span style={{ color: "#334155", fontSize: 11 }}>{value}</span>
      {data?.Asset_Class && (
        <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>
          {data.Asset_Class}
        </span>
      )}
    </Box>
  );
}

function PlaceholderRenderer() {
  return <span style={{ color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>—</span>;
}

// ─── Column builder ───────────────────────────────────────────────────────────

function buildColumns(varMode) {
  const varCurrent = varMode === "100D" ? "VaR_100D"      : "VaR_10D";
  const varDelta   = varMode === "100D" ? "Delta_100D"    : "Delta_10D";
  const varDeltaT1 = varMode === "100D" ? "Delta_100D_t1" : "Delta_10D_t1";

  return [
    {
      field: "Product",
      headerName: "Product",
      cellRenderer: ProductNameRenderer,
      flex: 2, minWidth: 200, sortable: false,
      cellStyle: { display: "flex", alignItems: "center", justifyContent: "flex-start" },
    },
    {
      headerName: "VAR",
      children: [
        { field: varCurrent,  headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 90, type: "numericColumn", sortable: false },
        { field: varDelta,    headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90, type: "numericColumn", sortable: false },
        { field: varDeltaT1,  headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90, type: "numericColumn", sortable: false },
      ],
    },
    {
      headerName: "1D P&L",
      children: [
        { field: "_pnl1d", headerName: "coming soon", cellRenderer: PlaceholderRenderer, flex: 1, minWidth: 100, sortable: false },
      ],
    },
    {
      headerName: "5D P&L",
      children: [
        { field: "_pnl5d", headerName: "coming soon", cellRenderer: PlaceholderRenderer, flex: 1, minWidth: 100, sortable: false },
      ],
    },
    {
      headerName: "INIT. MARGIN",
      children: [
        { field: "Margin",          headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 100, type: "numericColumn", sortable: false },
        { field: "Delta_Margin",    headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
        { field: "Delta_Margin_t1", headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
      ],
    },
  ];
}

const DEFAULT_COL_DEF = {
  resizable: true,
  suppressMovable: true,
  cellStyle: { fontSize: 11, display: "flex", alignItems: "center", justifyContent: "flex-end" },
};

// ─── VarToggle ────────────────────────────────────────────────────────────────

function VarToggle({ varMode, setVarMode }) {
  return (
    <ToggleButtonGroup
      value={varMode} exclusive
      onChange={(_, val) => { if (val) setVarMode(val); }}
      size="small"
      sx={{
        background: "#e2e8f0", borderRadius: "6px", padding: "2px", gap: "2px",
        "& .MuiToggleButton-root": {
          fontSize: 10, fontWeight: 700, padding: "1px 10px",
          border: "1px solid transparent", color: "#94a3b8",
          textTransform: "none", letterSpacing: "0.04em", borderRadius: "4px !important",
          "&.Mui-selected": {
            background: "#fff", color: "#0f172a",
            boxShadow: "0 1px 2px rgba(0,0,0,0.10)",
            "&:hover": { background: "#f8fafc" },
          },
        },
      }}
    >
      <ToggleButton value="100D">100D</ToggleButton>
      <ToggleButton value="10D">10D</ToggleButton>
    </ToggleButtonGroup>
  );
}

// ─── Row styling ──────────────────────────────────────────────────────────────

function makeGetRowStyle() {
  return ({ data }) => {
    const colour = data?._sectionColour ?? "#94a3b8";
    if (data?._rowType === "section") {
      return {
        background:   `${colour}1a`,
        borderLeft:   `4px solid ${colour}`,
        borderBottom: `2px solid ${colour}50`,
      };
    }
    if (data?._rowType === "subgroup") {
      return {
        background:   `${colour}0d`,
        borderLeft:   `3px solid ${colour}`,
        borderBottom: `1px solid ${colour}30`,
      };
    }
    return {
      borderLeft:   `3px solid ${colour}40`,
      background:   "#f8fafc",
      borderBottom: "1px solid #e9edf2",
    };
  };
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function RollRiskTab({ location, refreshKey }) {
  const [sections,  setSections]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [varMode,   setVarMode]   = useState("100D");

  useEffect(() => {
    setLoading(true); setError(null);
    getRollRisk(location)
      .then(r => {
        const coloured = (r.data.sections || []).map(sec => ({
          ...sec,
          rows: sec.rows.map(row => ({
            ...row,
            _sectionColour: SECTION_COLOURS[sec.section] ?? "#94a3b8",
          })),
        }));
        setSections(coloured);
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [location, refreshKey]);

  const colDefs     = useMemo(() => buildColumns(varMode), [varMode]);
  const getRowStyle = useCallback(makeGetRowStyle(), []);

  if (loading) return <Box sx={{ p: 2.5, color: "#94a3b8", fontSize: 12 }}>Loading...</Box>;
  if (error)   return <Box sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {error}</Box>;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0 }}>

      {/* ── Metrics bar ── */}
      <RollMetricsBar sections={sections} />

      {/* ── Header row ── */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
        <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>
          Roll Risk
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <VarToggle varMode={varMode} setVarMode={setVarMode} />
          <Typography sx={{ fontSize: 11, color: "#94a3b8" }}>Values in USD</Typography>
        </Box>
      </Box>

      {/* ── Section cards ── */}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {sections.map(sec => (
          <Card
            key={sec.section}
            elevation={0}
            sx={{ borderRadius: 2, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
          >
            <CardContent sx={{ p: "16px !important" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
                <Box sx={{
                  width: 10, height: 10, borderRadius: "50%",
                  background: SECTION_COLOURS[sec.section] ?? "#94a3b8",
                  flexShrink: 0,
                }} />
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>
                  {sec.section}
                </Typography>
              </Box>

              {sec.rows.length === 0 ? (
                <Typography sx={{ color: "#94a3b8", fontSize: 12, p: 1 }}>
                  No data available.
                </Typography>
              ) : (
                <Box className="ag-theme-alpine" sx={{ width: "100%", ...GRID_VARS }}>
                  <AgGridReact
                    theme="legacy"
                    rowData={sec.rows}
                    columnDefs={colDefs}
                    defaultColDef={DEFAULT_COL_DEF}
                    domLayout="autoHeight"
                    getRowStyle={getRowStyle}
                    suppressCellFocus
                    suppressHorizontalScroll
                    headerHeight={30}
                    groupHeaderHeight={24}
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  );
}
