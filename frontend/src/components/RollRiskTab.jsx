/**
 * RollRiskTab.jsx
 * Roll Risk tab — two views toggled at top:
 *
 *   RISK  — Fixed Income (currency subgroups) + Equities. Full rates breakdown
 *           shows offsetting STIRs effect. Section total = Cumulus netted Rates/Equities.
 *
 *   ROLLS — FI Rolls + Equity Rolls. Flat bond/equity list under each section.
 *           Section total = Cumulus netted from FI Rolls / Equity Rolls asset class.
 *           No subgroups. Product iVaRs are informational.
 *
 * Clicking a product row opens VarMarginChart inline below the section.
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
import { getFiGroupRisk, getFiRollRisk, getHawkRollPnl, getVixMargin, getMetrics } from "../api/client";
import { calcUtilisation, utilisationColour } from "../utils/limitUtilisation";
import VarMarginChart from "./VarMarginChart";

// ─── Section colours ──────────────────────────────────────────────────────────

const SECTION_COLOURS = {
  // Risk view
  "Fixed Income": "#3b82f6",
  "Equities":     "#ec4899",
  // Rolls view
  "FI Rolls":     "#f59e0b",
  "Equity Rolls": "#10b981",
};

const TOTAL_COLOUR = "#8b5cf6";

// ─── Grid CSS vars ────────────────────────────────────────────────────────────

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
  return { text: `${up ? "▲" : "▼"} $${Math.abs(delta / 1_000_000).toFixed(1)}M from SOD`, up };
}
function fmtDeltaK(delta) {
  if (delta === null || delta === undefined || isNaN(delta)) return null;
  const up = delta >= 0;
  return { text: `${up ? "▲" : "▼"} $${Math.abs(Math.round(delta / 1000)).toLocaleString("en-GB")}K from SOD`, up };
}

// ─── Metrics helpers ──────────────────────────────────────────────────────────

function deriveMetrics(sections) {
  const totals = { margin: 0, marginDelta: 0, var: 0, varDelta: 0 };
  const bySection = {};
  for (const sec of sections) {
    const r = sec.rows.find(r => r._rowType === "section");
    bySection[sec.section] = {
      margin: r?.Margin ?? 0,       marginDelta: r?.Delta_Margin ?? 0,
      var:    r?.VaR_100D ?? 0,     varDelta:    r?.Delta_100D   ?? 0,
    };
    totals.margin      += bySection[sec.section].margin;
    totals.marginDelta += bySection[sec.section].marginDelta;
    totals.var         += bySection[sec.section].var;
    totals.varDelta    += bySection[sec.section].varDelta;
  }
  return { totals, bySection };
}

// ─── Metric card ──────────────────────────────────────────────────────────────

function RollMetricCard({ label, value, change, colour, valueColour, vixLabel }) {
  return (
    <Card elevation={0} sx={{ borderRadius: 2, borderTop: `3px solid ${colour}`, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", background: "#fff" }}>
      <CardContent sx={{ p: "12px 14px !important" }}>
        <Typography sx={{ fontSize: 10, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", mb: 0.5 }}>
          {label}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, mb: 0.25 }}>
          <Typography sx={{ fontSize: 20, fontWeight: 700, color: valueColour ?? "#0f172a" }}>
            {value}
          </Typography>
          {vixLabel && (
            <Typography sx={{ fontSize: 11, fontWeight: 600, color: "#64748b", whiteSpace: "nowrap" }}>
              {vixLabel}
            </Typography>
          )}
        </Box>
        {change
          ? <Typography sx={{ fontSize: 10, fontWeight: 500, color: change.up ? "#ef4444" : "#22c55e" }}>{change.text}</Typography>
          : <Typography sx={{ fontSize: 10 }}>&nbsp;</Typography>
        }
      </CardContent>
    </Card>
  );
}

// ─── Metrics bar (adapts labels to current view) ──────────────────────────────

function RollMetricsBar({ sections, view, vix, metrics }) {
  const { totals, bySection } = useMemo(() => deriveMetrics(sections), [sections]);

  const isRolls = view === "rolls";
  const s1key   = isRolls ? "FI Rolls"     : "Fixed Income";
  const s2key   = isRolls ? "Equity Rolls" : "Equities";
  const s1label = isRolls ? "FI Rolls"     : "FI";
  const s2label = isRolls ? "Equity Rolls" : "Equity";
  const s1 = bySection[s1key] ?? {};
  const s2 = bySection[s2key] ?? {};

  const vixCurrent   = vix?.vix_current ?? 0;
  const vixSod       = vix?.vix_sod     ?? 0;
  // Use OfficeRisk margin (same source as MetricsRow) — not section-derived margin
  const utilRatio    = calcUtilisation(metrics?.margin_current, vixCurrent);
  const utilSodRatio = calcUtilisation(metrics?.margin_sod,     vixSod);
  const utilDelta    = utilRatio != null && utilSodRatio != null ? utilRatio - utilSodRatio : null;

  function fmtPct(val) {
    if (val == null || isNaN(val)) return "—";
    return `${(val * 100).toFixed(1)}%`;
  }
  function fmtDeltaPct(delta) {
    if (delta == null || isNaN(delta)) return null;
    const up = delta >= 0;
    return { text: `${up ? "▲" : "▼"} ${Math.abs(delta * 100).toFixed(1)}pp from SOD`, up };
  }

  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1.5, mb: 2 }}>
      <RollMetricCard label="Total Roll Margin"         value={fmtM(totals.margin)} change={fmtDeltaM(totals.marginDelta)} colour={TOTAL_COLOUR} />
      <RollMetricCard label={`${s1label} Margin`}       value={fmtM(s1.margin)}     change={fmtDeltaM(s1.marginDelta)}     colour={SECTION_COLOURS[s1key]} />
      <RollMetricCard label={`${s2label} Margin`}       value={fmtM(s2.margin)}     change={fmtDeltaM(s2.marginDelta)}     colour={SECTION_COLOURS[s2key]} />
      <RollMetricCard label="Total Roll VaR 100D"       value={fmtK(totals.var)}    change={fmtDeltaK(totals.varDelta)}    colour={TOTAL_COLOUR} />
      <RollMetricCard label={`${s1label} VaR 100D`}     value={fmtK(s1.var)}        change={fmtDeltaK(s1.varDelta)}        colour={SECTION_COLOURS[s1key]} />
      <RollMetricCard label={`${s2label} VaR 100D`}     value={fmtK(s2.var)}        change={fmtDeltaK(s2.varDelta)}        colour={SECTION_COLOURS[s2key]} />
      <RollMetricCard
        label="Limit Utilisation"
        value={fmtPct(utilRatio)}
        change={fmtDeltaPct(utilDelta)}
        colour="#8b5cf6"
        valueColour={utilisationColour(utilRatio)}
        vixLabel={vixCurrent ? `VIX IM: ${fmtM(vixCurrent)}` : null}
      />
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
  const isSection  = data?._rowType === "section";
  const isSubgroup = data?._rowType === "subgroup";
  return (
    <span style={{
      fontWeight: (isSection || isSubgroup) ? 700 : 400,
      color:      isSection ? "#0f172a" : isSubgroup ? "#1e293b" : "#334155",
      fontSize:   isSection ? 12 : 11,
    }}>
      {Math.round(Math.abs(value)).toLocaleString("en-GB")}
    </span>
  );
}

function ProductNameRenderer({ value, data }) {
  const colour = data?._sectionColour ?? "#94a3b8";

  if (data?._rowType === "section") {
    return (
      <span style={{ color: colour, fontWeight: 800, fontSize: 12, letterSpacing: "0.04em", paddingLeft: 4 }}>
        {value}
      </span>
    );
  }
  if (data?._rowType === "subgroup") {
    return (
      <span style={{ color: colour, fontWeight: 700, fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", paddingLeft: 8 }}>
        {value}
      </span>
    );
  }
  return (
    <Box sx={{ pl: 3, display: "flex", alignItems: "center", cursor: "pointer" }}>
      <span style={{ color: colour, marginRight: 6 }}>└</span>
      <span style={{ color: "#334155", fontSize: 11 }}>{value}</span>
      {data?.Asset_Class && (
        <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>{data.Asset_Class}</span>
      )}
      <span style={{ color: "#3b82f6", marginLeft: 8, fontSize: 9, opacity: 0.7 }}>▶ chart</span>
    </Box>
  );
}

function PnLRenderer({ value, data }) {
  if (value === null || value === undefined || data?._rowType === "section" || data?._rowType === "subgroup")
    return <span style={{ color: "#94a3b8" }}>—</span>;
  const pos = value >= 0;
  return (
    <span style={{ color: pos ? "#22c55e" : "#ef4444", fontWeight: 500, fontSize: 11 }}>
      {pos ? "" : "-"}{Math.abs(Math.round(value)).toLocaleString("en-GB")}
    </span>
  );
}

// ─── Columns ──────────────────────────────────────────────────────────────────

function buildColumns(varMode) {
  const varCurrent = varMode === "100D" ? "VaR_100D"      : "VaR_10D";
  const varDelta   = varMode === "100D" ? "Delta_100D"    : "Delta_10D";
  const varDeltaT1 = varMode === "100D" ? "Delta_100D_t1" : "Delta_10D_t1";
  return [
    {
      field: "Product", headerName: "Product", cellRenderer: ProductNameRenderer,
      flex: 2, minWidth: 200, sortable: false,
      cellStyle: { display: "flex", alignItems: "center", justifyContent: "flex-start" },
    },
    {
      headerName: "VAR", children: [
        { field: varCurrent,  headerName: "Current",  cellRenderer: NumRenderer,   flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
        { field: varDelta,    headerName: "Δ SOD",    cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
        { field: varDeltaT1,  headerName: "Δ t-1",    cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
      ],
    },
    {
      headerName: "1D P&L", children: [
        { field: "_pnl1d", headerName: "Gross P&L",  cellRenderer: PnLRenderer, flex: 1, minWidth: 100, type: "numericColumn", sortable: false },
      ],
    },
    {
      headerName: "5D P&L", children: [
        { field: "_pnl5d", headerName: "Cumulative", cellRenderer: PnLRenderer, flex: 1, minWidth: 100, type: "numericColumn", sortable: false },
      ],
    },
    {
      headerName: "INIT. MARGIN", children: [
        { field: "Margin",          headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 100, type: "numericColumn", sortable: false },
        { field: "Delta_Margin",    headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
        { field: "Delta_Margin_t1", headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: false },
      ],
    },
  ];
}

const DEFAULT_COL_DEF = {
  resizable: true, suppressMovable: true,
  cellStyle: { fontSize: 11, display: "flex", alignItems: "center", justifyContent: "flex-end" },
};

// ─── Row styling ──────────────────────────────────────────────────────────────

function makeGetRowStyle(selectedProduct) {
  return ({ data }) => {
    const colour   = data?._sectionColour ?? "#94a3b8";
    const selected = data?._rowType === "product" && data?.Product === selectedProduct;
    if (data?._rowType === "section")  return { background: `${colour}1a`, borderLeft: `4px solid ${colour}`, borderBottom: `2px solid ${colour}50` };
    if (data?._rowType === "subgroup") return { background: `${colour}0d`, borderLeft: `3px solid ${colour}`, borderBottom: `1px solid ${colour}30` };
    if (selected)                      return { background: `${colour}20`, borderLeft: `3px solid ${colour}`, borderBottom: "1px solid #e9edf2", fontWeight: 700 };
    return { borderLeft: `3px solid ${colour}40`, background: "#f8fafc", borderBottom: "1px solid #e9edf2" };
  };
}

// ─── Toggles ─────────────────────────────────────────────────────────────────

function ViewToggle({ view, setView }) {
  return (
    <ToggleButtonGroup
      value={view} exclusive
      onChange={(_, val) => { if (val) setView(val); }}
      size="small"
      sx={{
        border: "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden",
        "& .MuiToggleButton-root": {
          fontSize: 11, fontWeight: 600, padding: "3px 14px",
          border: "none", color: "#64748b", textTransform: "none",
          "&.Mui-selected": {
            background: "#0f172a", color: "#fff",
            "&:hover": { background: "#1e293b" },
          },
        },
      }}
    >
      <ToggleButton value="risk">Risk</ToggleButton>
      <ToggleButton value="rolls">Rolls</ToggleButton>
    </ToggleButtonGroup>
  );
}

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

// ─── Section card ─────────────────────────────────────────────────────────────

function SectionCard({ sec, colDefs, selectedProduct, setSelectedProduct, location, refreshKey }) {
  const colour      = SECTION_COLOURS[sec.section] ?? "#94a3b8";
  const getRowStyle = useCallback(makeGetRowStyle(selectedProduct), [selectedProduct]);

  const onRowClicked = useCallback(({ data }) => {
    if (data?._rowType !== "product") return;
    setSelectedProduct(prev =>
      prev?.product === data.Product && prev?.section === sec.section
        ? null
        : { product: data.Product, section: sec.section }
    );
  }, [sec.section, setSelectedProduct]);

  const isChartOpen = selectedProduct?.section === sec.section;

  return (
    <Card elevation={0} sx={{ borderRadius: 2, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
      <CardContent sx={{ p: "16px !important" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
          <Box sx={{ width: 10, height: 10, borderRadius: "50%", background: colour, flexShrink: 0 }} />
          <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>{sec.section}</Typography>
        </Box>

        {sec.rows.length === 0 ? (
          <Typography sx={{ color: "#94a3b8", fontSize: 12, p: 1 }}>No data available.</Typography>
        ) : (
          <Box className="ag-theme-alpine" sx={{ width: "100%", ...GRID_VARS }}>
            <AgGridReact
              theme="legacy"
              rowData={sec.rows}
              columnDefs={colDefs}
              defaultColDef={DEFAULT_COL_DEF}
              domLayout="autoHeight"
              getRowStyle={getRowStyle}
              onRowClicked={onRowClicked}
              suppressCellFocus
              suppressHorizontalScroll
              headerHeight={30}
              groupHeaderHeight={24}
            />
          </Box>
        )}

        {isChartOpen && (
          <Box sx={{ mt: 2 }}>
            <VarMarginChart
              location={location}
              chartProduct={selectedProduct.product}
              chartLabel={selectedProduct.product}
              onReset={() => setSelectedProduct(null)}
              refreshKey={refreshKey}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function RollRiskTab({ location, refreshKey }) {
  const [view,            setView]            = useState("risk");
  const [riskSections,    setRiskSections]    = useState([]);
  const [rollsSections,   setRollsSections]   = useState([]);
  const [loadingRisk,     setLoadingRisk]     = useState(true);
  const [loadingRolls,    setLoadingRolls]    = useState(true);
  const [errorRisk,       setErrorRisk]       = useState(null);
  const [errorRolls,      setErrorRolls]      = useState(null);
  const [varMode,         setVarMode]         = useState("100D");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [vix,             setVix]             = useState(null);
  const [metrics,         setMetrics]         = useState(null);

  const colourSections = (data, colourMap) =>
    (data || []).map(sec => ({
      ...sec,
      rows: sec.rows.map(row => ({ ...row, _sectionColour: colourMap[sec.section] ?? "#94a3b8" })),
    }));

  // Helper: build pnlMap from hawk-roll-pnl response
  const buildPnlMap = (pnlRows) => {
    const map = {};
    for (const r of pnlRows) map[r.Product] = { _pnl1d: r.PnL_1D, _pnl5d: r.PnL_5D };
    return map;
  };

  // Helper: inject P&L into section rows by Product name
  const mergePnl = (sections, pnlMap) =>
    sections.map(sec => ({
      ...sec,
      rows: sec.rows.map(row => ({
        ...row,
        _pnl1d: row._rowType === "product" ? (pnlMap[row.Product]?._pnl1d ?? null) : null,
        _pnl5d: row._rowType === "product" ? (pnlMap[row.Product]?._pnl5d ?? null) : null,
      })),
    }));

  // Fetch Risk view + P&L + VIX + metrics in parallel
  useEffect(() => {
    setLoadingRisk(true); setErrorRisk(null);
    Promise.all([getFiGroupRisk(location), getHawkRollPnl(), getVixMargin(), getMetrics(location, 95.0, 100)])
      .then(([riskRes, pnlRes, vixRes, metricsRes]) => {
        const pnlMap   = buildPnlMap(pnlRes.data.data || []);
        const sections = colourSections(riskRes.data.sections, SECTION_COLOURS);
        setRiskSections(mergePnl(sections, pnlMap));
        setVix(vixRes);
        setMetrics(metricsRes.data);
        setLoadingRisk(false);
      })
      .catch(e => { setErrorRisk(e.message); setLoadingRisk(false); });
  }, [location, refreshKey]);

  // Fetch Rolls view + P&L + VIX + metrics in parallel
  useEffect(() => {
    setLoadingRolls(true); setErrorRolls(null);
    Promise.all([getFiRollRisk(location), getHawkRollPnl(), getVixMargin(), getMetrics(location, 95.0, 100)])
      .then(([rollsRes, pnlRes, vixRes, metricsRes]) => {
        const pnlMap   = buildPnlMap(pnlRes.data.data || []);
        const sections = colourSections(rollsRes.data.sections, SECTION_COLOURS);
        setRollsSections(mergePnl(sections, pnlMap));
        setVix(vixRes);
        setMetrics(metricsRes.data);
        setLoadingRolls(false);
      })
      .catch(e => { setErrorRolls(e.message); setLoadingRolls(false); });
  }, [location, refreshKey]);

  // Reset on location or view change
  useEffect(() => { setSelectedProduct(null); }, [location, view]);

  const sections = view === "risk" ? riskSections  : rollsSections;
  const loading  = view === "risk" ? loadingRisk   : loadingRolls;
  const error    = view === "risk" ? errorRisk     : errorRolls;
  const colDefs  = useMemo(() => buildColumns(varMode), [varMode]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0 }}>

      {/* ── Metrics bar ── */}
      {!loading && !error && <RollMetricsBar sections={sections} view={view} vix={vix} metrics={metrics} />}

      {/* ── Toolbar ── */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Roll Risk</Typography>
          <ViewToggle view={view} setView={setView} />
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <VarToggle varMode={varMode} setVarMode={setVarMode} />
          <Typography sx={{ fontSize: 11, color: "#94a3b8" }}>Values in USD</Typography>
        </Box>
      </Box>

      {/* ── Content ── */}
      {loading ? (
        <Box sx={{ p: 2.5, color: "#94a3b8", fontSize: 12 }}>Loading...</Box>
      ) : error ? (
        <Box sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {error}</Box>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
          {sections.map(sec => (
            <SectionCard
              key={sec.section}
              sec={sec}
              colDefs={colDefs}
              selectedProduct={selectedProduct}
              setSelectedProduct={setSelectedProduct}
              location={location}
              refreshKey={refreshKey}
            />
          ))}
        </Box>
      )}

    </Box>
  );
}
