/**
 * AnalystTab.jsx
 * Side-by-side layout: analyst table (left) + detail panel (right).
 * Clicking a product row switches the VaR chart to that product's iVaR history.
 * Axis labels auto-scale: raw / K / M depending on data magnitude.
 */
import React, { useEffect, useState, useMemo, useCallback } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
ModuleRegistry.registerModules([AllCommunityModule]);

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Typography from "@mui/material/Typography";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";

import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

import { getAnalysts, getAnalystChart, getAnalystProducts, getAnalystProductChart } from "../api/client";

// ─── Constants ────────────────────────────────────────────────────────────────

const NAVBAR_HEIGHT = 48;
const PAGE_PAD      = 32;
const PANEL_HEIGHT  = `calc(100vh - ${NAVBAR_HEIGHT + PAGE_PAD}px)`;

// ─── Smart axis formatter ─────────────────────────────────────────────────────

function makeFormatter(data, key) {
  const max = Math.max(...data.map(d => Math.abs(d[key] ?? 0)));
  if (max >= 1_000_000) return v => `${(Math.abs(v) / 1_000_000).toFixed(1)}M`;
  if (max >= 10_000)    return v => `${(Math.abs(v) / 1000).toFixed(0)}K`;
  return v => Math.abs(v).toLocaleString("en-GB");
}

function makeTooltipFormatter(data, key, label) {
  const max = Math.max(...data.map(d => Math.abs(d[key] ?? 0)));
  if (max >= 1_000_000) return v => [`${(Math.abs(v) / 1_000_000).toFixed(2)}M`, label];
  if (max >= 10_000)    return v => [`${(Math.abs(v) / 1000).toFixed(1)}K`, label];
  return v => [Math.abs(v).toLocaleString("en-GB"), label];
}

// ─── Cell renderers ───────────────────────────────────────────────────────────

function AnalystNameRenderer({ value, data }) {
  return (
    <Box sx={{ pl: 1 }}>
      <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#0f172a", lineHeight: 1.2 }}>{value}</Typography>
      <Typography sx={{ fontSize: 10, color: "#94a3b8", lineHeight: 1.2 }}>{data?.Office}</Typography>
    </Box>
  );
}

function NumRenderer({ value }) {
  if (value === null || value === undefined) return <span style={{ color: "#94a3b8" }}>—</span>;
  return <span>{Math.round(Math.abs(value)).toLocaleString("en-GB")}</span>;
}

function DeltaRenderer({ value }) {
  if (value === null || value === undefined || value === "") return <span style={{ color: "#94a3b8" }}>—</span>;
  const up = value >= 0;
  return (
    <span style={{ color: up ? "#ef4444" : "#22c55e", fontWeight: 500, fontSize: 11 }}>
      {up ? "▲" : "▼"} {Math.abs(Math.round(value)).toLocaleString("en-GB")}
    </span>
  );
}

function ProductNameRenderer({ value, data }) {
  return (
    <Box sx={{ pl: 1 }}>
      <span style={{ color: "#334155", fontSize: 11 }}>{value}</span>
      {data?.Asset_Class && (
        <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>{data.Asset_Class}</span>
      )}
    </Box>
  );
}

// ─── Column defs ─────────────────────────────────────────────────────────────

function buildAnalystCols(varMode) {
  const cur  = varMode === "100D" ? "VaR_100D"      : "VaR_10D";
  const dSOD = varMode === "100D" ? "Delta_100D"    : "Delta_10D";
  const dT1  = varMode === "100D" ? "Delta_100D_t1" : "Delta_10D_t1";
  return [
    {
      field: "Analyst", headerName: "Analyst",
      cellRenderer: AnalystNameRenderer,
      flex: 2, minWidth: 120,
      cellStyle: { display: "flex", alignItems: "center" },
    },
    {
      headerName: "VaR",
      children: [
        { field: cur,  headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 80, type: "numericColumn", sort: "desc" },
        { field: dSOD, headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 80, type: "numericColumn" },
        { field: dT1,  headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 80, type: "numericColumn" },
      ],
    },
    {
      headerName: "Margin",
      children: [
        { field: "Margin",       headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 85, type: "numericColumn" },
        { field: "Delta_Margin", headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 80, type: "numericColumn" },
      ],
    },
  ];
}

function buildProductCols(onProductClick, selectedProduct) {
  return [
    {
      field: "Product", headerName: "Product",
      cellRenderer: ({ value, data }) => (
        <Box sx={{ pl: 1, cursor: "pointer" }}>
          <span style={{
            color: selectedProduct === value ? "#3b82f6" : "#334155",
            fontSize: 11,
            fontWeight: selectedProduct === value ? 600 : 400,
          }}>{value}</span>
          {data?.Asset_Class && (
            <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>{data.Asset_Class}</span>
          )}
        </Box>
      ),
      flex: 2, minWidth: 160,
      cellStyle: { display: "flex", alignItems: "center" },
      onCellClicked: ({ data }) => onProductClick(data?.Product),
    },
    { field: "iVaR",          headerName: "iVaR",  cellRenderer: NumRenderer,   flex: 1, minWidth: 70, type: "numericColumn", sort: "desc" },
    { field: "Delta_iVaR",    headerName: "Δ SOD", cellRenderer: DeltaRenderer, flex: 1, minWidth: 70, type: "numericColumn" },
    { field: "Delta_iVaR_t1", headerName: "Δ t-1", cellRenderer: DeltaRenderer, flex: 1, minWidth: 70, type: "numericColumn" },
    { field: "Margin",        headerName: "Margin", cellRenderer: NumRenderer,  flex: 1, minWidth: 70, type: "numericColumn" },
  ];
}

// ─── Grid defaults ────────────────────────────────────────────────────────────

const DEFAULT_COL = {
  resizable: true,
  suppressMovable: true,
  cellStyle: { fontSize: 12, display: "flex", alignItems: "center", justifyContent: "flex-end" },
};

const GRID_VARS = {
  "--ag-header-background-color":  "#f8fafc",
  "--ag-odd-row-background-color": "#fff",
  "--ag-row-hover-color":          "#f0f7ff",
  "--ag-border-color":             "#e2e8f0",
  "--ag-header-foreground-color":  "#64748b",
  "--ag-font-size":                "12px",
  "--ag-cell-horizontal-padding":  "8px",
  "--ag-row-height":               "40px",
  "--ag-header-height":            "32px",
  "--ag-borders":                  "none",
  "--ag-row-border-style":         "solid",
  "--ag-row-border-width":         "1px",
  "--ag-row-border-color":         "#f1f5f9",
};

// ─── Toggles ──────────────────────────────────────────────────────────────────

function VarToggle({ varMode, setVarMode }) {
  return (
    <ToggleButtonGroup value={varMode} exclusive size="small"
      onChange={(_, val) => { if (val) setVarMode(val); }}
      sx={{
        background: "#e2e8f0", borderRadius: "6px", padding: "2px",
        "& .MuiToggleButton-root": {
          fontSize: 10, fontWeight: 700, padding: "1px 10px",
          border: "1px solid transparent", color: "#94a3b8",
          textTransform: "none", borderRadius: "4px !important",
          "&.Mui-selected": { background: "#fff", color: "#0f172a", boxShadow: "0 1px 2px rgba(0,0,0,0.10)" },
        },
      }}
    >
      <ToggleButton value="100D">100D</ToggleButton>
      <ToggleButton value="10D">10D</ToggleButton>
    </ToggleButtonGroup>
  );
}

function DaysToggle({ days, setDays }) {
  return (
    <ToggleButtonGroup value={String(days)} exclusive size="small"
      onChange={(_, val) => { if (val) setDays(Number(val)); }}
      sx={{
        background: "#e2e8f0", borderRadius: "6px", padding: "2px",
        "& .MuiToggleButton-root": {
          fontSize: 10, fontWeight: 700, padding: "1px 10px",
          border: "1px solid transparent", color: "#94a3b8",
          textTransform: "none", borderRadius: "4px !important",
          "&.Mui-selected": { background: "#fff", color: "#0f172a", boxShadow: "0 1px 2px rgba(0,0,0,0.10)" },
        },
      }}
    >
      <ToggleButton value="5">5D</ToggleButton>
      <ToggleButton value="30">1M</ToggleButton>
      <ToggleButton value="90">3M</ToggleButton>
    </ToggleButtonGroup>
  );
}

// ─── Mini area chart ──────────────────────────────────────────────────────────

function MiniChart({ data, dataKey, color, label, loading }) {
  const axisFmt    = data.length ? makeFormatter(data, dataKey) : v => v;
  const tooltipFmt = data.length ? makeTooltipFormatter(data, dataKey, label) : v => [v, label];

  return (
    <Box sx={{ mb: 2 }}>
      <Typography sx={{ fontSize: 10, fontWeight: 700, color: "#94a3b8",
        textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.75 }}>
        {label}
      </Typography>
      {loading ? (
        <Box sx={{ height: 130, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>Loading...</Typography>
        </Box>
      ) : data.length === 0 ? (
        <Box sx={{ height: 130, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>No data.</Typography>
        </Box>
      ) : (
        <Box sx={{ height: 130 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={color} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="Date" tick={{ fontSize: 9, fill: "#94a3b8" }} tickLine={false} />
              <YAxis width={42} tick={{ fontSize: 9, fill: color }} tickLine={false} axisLine={false}
                tickFormatter={axisFmt} />
              <Tooltip
                formatter={tooltipFmt}
                contentStyle={{ fontSize: 11, borderRadius: 6, border: "1px solid #e2e8f0" }}
              />
              <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2}
                fill={`url(#grad-${dataKey})`} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Box>
      )}
    </Box>
  );
}

// ─── Right panel: analyst detail ─────────────────────────────────────────────

function AnalystDetail({ analyst, office, varMode }) {
  const [chartDays,       setChartDays]       = useState(30);
  const [analystChart,    setAnalystChart]     = useState([]);
  const [chartLoading,    setChartLoading]     = useState(true);
  const [products,        setProducts]         = useState([]);
  const [prodLoading,     setProdLoading]      = useState(true);
  const [selectedProduct, setSelectedProduct]  = useState(null);
  const [productChart,    setProductChart]     = useState([]);
  const [prodChartLoad,   setProdChartLoad]    = useState(false);

  const confidence = varMode === "100D" ? 95.0 : 100.0;
  const lookback   = varMode === "100D" ? 100  : 10;

  // Analyst-level chart
  useEffect(() => {
    setChartLoading(true);
    setSelectedProduct(null);
    getAnalystChart(analyst, office, confidence, lookback, chartDays)
      .then(r => { setAnalystChart(r.data?.data || []); setChartLoading(false); })
      .catch(() => setChartLoading(false));
  }, [analyst, office, confidence, lookback, chartDays]);

  // Product list
  useEffect(() => {
    setProdLoading(true);
    setSelectedProduct(null);
    getAnalystProducts(analyst, office, confidence, lookback)
      .then(r => { setProducts(r.data?.data || []); setProdLoading(false); })
      .catch(() => setProdLoading(false));
  }, [analyst, office, confidence, lookback]);

  // Product-level chart (triggered when a product is selected)
  useEffect(() => {
    if (!selectedProduct) return;
    setProdChartLoad(true);
    getAnalystProductChart(analyst, office, selectedProduct, confidence, lookback, chartDays)
      .then(r => { setProductChart(r.data?.data || []); setProdChartLoad(false); })
      .catch(() => setProdChartLoad(false));
  }, [analyst, office, selectedProduct, confidence, lookback, chartDays]);

  const handleProductClick = useCallback((product) => {
    setSelectedProduct(prev => prev === product ? null : product);
  }, []);

  const productCols = useMemo(
    () => buildProductCols(handleProductClick, selectedProduct),
    [handleProductClick, selectedProduct]
  );

  // Which data drives the VaR chart
  const varChartData    = selectedProduct ? productChart : analystChart;
  const varChartLoading = selectedProduct ? prodChartLoad : chartLoading;
  const varChartKey     = selectedProduct || "VaR";
  const varChartLabel   = selectedProduct ? `iVaR — ${selectedProduct}` : "VaR History";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        px: 2, pt: 2, pb: 1.5, borderBottom: "1px solid #f1f5f9", flexShrink: 0 }}>
        <Box>
          <Typography sx={{ fontSize: 16, fontWeight: 700, color: "#0f172a", lineHeight: 1.2 }}>
            {analyst}
          </Typography>
          <Typography sx={{ fontSize: 11, color: "#64748b", mt: 0.25 }}>{office}</Typography>
        </Box>
        <DaysToggle days={chartDays} setDays={setChartDays} />
      </Box>

      {/* Scrollable body */}
      <Box sx={{ flex: 1, overflowY: "auto", px: 2, py: 1.5 }}>

        {/* VaR / iVaR chart — switches to product when one is selected */}
        {selectedProduct && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Typography sx={{ fontSize: 10, color: "#3b82f6", fontWeight: 600 }}>
              {selectedProduct}
            </Typography>
            <Typography
              onClick={() => setSelectedProduct(null)}
              sx={{ fontSize: 10, color: "#94a3b8", cursor: "pointer",
                "&:hover": { color: "#64748b" } }}
            >
              ✕ Back to total
            </Typography>
          </Box>
        )}

        <MiniChart
          data={varChartData}
          dataKey={selectedProduct ? "iVaR" : "VaR"}
          color="#ef4444"
          label={varChartLabel}
          loading={varChartLoading}
        />

        {/* Margin chart — always analyst-level */}
        <MiniChart
          data={analystChart}
          dataKey="Margin"
          color="#3b82f6"
          label="Margin History"
          loading={chartLoading}
        />

        {/* Product breakdown */}
        <Typography sx={{ fontSize: 10, fontWeight: 700, color: "#94a3b8",
          textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.5 }}>
          Product Breakdown
          <Typography component="span" sx={{ fontSize: 10, color: "#94a3b8", ml: 1,
            fontWeight: 400, textTransform: "none" }}>
            — click a row to drill into its chart
          </Typography>
        </Typography>

        {prodLoading ? (
          <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>Loading...</Typography>
        ) : products.length === 0 ? (
          <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>No product data.</Typography>
        ) : (
          <Box className="ag-theme-alpine" sx={{ width: "100%", ...GRID_VARS,
            "--ag-row-height": "30px", "--ag-header-height": "28px", "--ag-font-size": "11px",
            "--ag-row-hover-color": "#f0f7ff",
          }}>
            <AgGridReact
              theme="legacy"
              rowData={products}
              columnDefs={productCols}
              defaultColDef={DEFAULT_COL}
              domLayout="autoHeight"
              suppressCellFocus
              suppressHorizontalScroll
              headerHeight={28}
              getRowStyle={({ data: row }) => ({
                background: selectedProduct === row?.Product ? "#eff6ff" : "#fff",
                cursor: "pointer",
                borderLeft: selectedProduct === row?.Product ? "2px solid #3b82f6" : "2px solid transparent",
              })}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
}

// ─── Right panel: empty state ─────────────────────────────────────────────────

function EmptyDetail() {
  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 1 }}>
      <Typography sx={{ fontSize: 32, opacity: 0.12 }}>←</Typography>
      <Typography sx={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>Select an analyst</Typography>
      <Typography sx={{ fontSize: 11, color: "#cbd5e1" }}>Click any row to view detail</Typography>
    </Box>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AnalystTab({ location, refreshKey }) {
  const [data,     setData]     = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [selected, setSelected] = useState(null);
  const [varMode,  setVarMode]  = useState("100D");

  useEffect(() => {
    setLoading(true); setError(null); setSelected(null);
    getAnalysts(location)
      .then(r => { setData(r.data?.data || []); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [location, refreshKey]);

  const handleRowClick = useCallback(({ data: row }) => {
    if (!row?.Analyst) return;
    setSelected(prev =>
      prev?.analyst === row.Analyst && prev?.office === row.Office
        ? null
        : { analyst: row.Analyst, office: row.Office }
    );
  }, []);

  const analystCols = useMemo(() => buildAnalystCols(varMode), [varMode]);

  const getRowStyle = useCallback(({ data: row }) => {
    const sel = selected?.analyst === row?.Analyst && selected?.office === row?.Office;
    return {
      borderLeft: sel ? "3px solid #3b82f6" : "3px solid transparent",
      background: sel ? "#eff6ff" : "#fff",
      cursor: "pointer",
    };
  }, [selected]);

  if (error) return <Box sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {error}</Box>;

  return (
    <Box sx={{ display: "flex", gap: 1.5, height: PANEL_HEIGHT }}>

      {/* ── Left: analyst table ── */}
      <Card elevation={0} sx={{
        flex: "0 0 55%", borderRadius: 2,
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center",
          px: 2, py: 1.5, borderBottom: "1px solid #f1f5f9", flexShrink: 0 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
            Analysts
            {!loading && (
              <Typography component="span" sx={{ fontSize: 11, color: "#94a3b8", ml: 1, fontWeight: 400 }}>
                {data.length} total
              </Typography>
            )}
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <VarToggle varMode={varMode} setVarMode={setVarMode} />
            <Typography sx={{ fontSize: 11, color: "#94a3b8" }}>USD</Typography>
          </Box>
        </Box>

        <Box sx={{ flex: 1, overflow: "hidden" }} className="ag-theme-alpine" style={GRID_VARS}>
          {loading ? (
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
              <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>Loading analysts...</Typography>
            </Box>
          ) : (
            <AgGridReact
              theme="legacy"
              rowData={data}
              columnDefs={analystCols}
              defaultColDef={DEFAULT_COL}
              getRowStyle={getRowStyle}
              onRowClicked={handleRowClick}
              suppressCellFocus
              suppressHorizontalScroll
              headerHeight={32}
              groupHeaderHeight={26}
            />
          )}
        </Box>
      </Card>

      {/* ── Right: detail panel ── */}
      <Card elevation={0} sx={{
        flex: 1, borderRadius: 2,
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        overflow: "hidden",
      }}>
        {selected
          ? <AnalystDetail key={selected.analyst} analyst={selected.analyst} office={selected.office} varMode={varMode} />
          : <EmptyDetail />
        }
      </Card>

    </Box>
  );
}
