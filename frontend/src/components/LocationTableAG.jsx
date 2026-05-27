/**
 * LocationTableAG.jsx
 * AG Grid replacement for LocationTable and LocationTable_New.
 *
 * Level 1: Office rows  — click to show sector breakdown below
 * Level 2: Sector rows  — click to expand product rows
 * Level 3: Product rows with subgroup header rows (injected by backend,
 *           carrying Cumulus netted VaR values)
 *
 * P&L columns (1D, 5D) sourced from HAWK parquet cache via /api/hawk-office-pnl.
 * Fetched in parallel with VaR data and merged client-side by Office name.
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
import { getLocationTable, getAssetClassTableGrouped, getProductTableBySector, getHawkOfficePnl } from "../api/client";

// ─── Constants ────────────────────────────────────────────────────────────────

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

// ─── Cell renderers ───────────────────────────────────────────────────────────

function DeltaRenderer({ value, data }) {
  if (data?._rowType === "subgroup" && (value === null || value === undefined))
    return <span style={{ color: "#94a3b8" }}>—</span>;
  if (value === null || value === undefined || value === "")
    return <span style={{ color: "#94a3b8" }}>—</span>;
  const up = value >= 0;
  const bold = data?._rowType === "subgroup";
  return (
    <span style={{ color: up ? "#ef4444" : "#22c55e", fontWeight: bold ? 700 : 500, fontSize: 11 }}>
      {up ? "▲" : "▼"} {Math.abs(Math.round(value)).toLocaleString("en-GB")}
    </span>
  );
}

function NumRenderer({ value, data }) {
  if (data?._rowType === "subgroup") {
    if (value === null || value === undefined)
      return <span style={{ color: "#94a3b8" }}>—</span>;
    return (
      <span style={{ fontWeight: 700, color: "#0f172a" }}>
        {Math.round(Math.abs(value)).toLocaleString("en-GB")}
      </span>
    );
  }
  if (value === null || value === undefined)
    return <span style={{ color: "#94a3b8" }}>—</span>;
  return <span>{Math.round(Math.abs(value)).toLocaleString("en-GB")}</span>;
}

function PnlRenderer({ value }) {
  if (value === null || value === undefined)
    return <span style={{ color: "#94a3b8" }}>—</span>;
  const positive = value >= 0;
  return (
    <span style={{ color: positive ? "#22c55e" : "#ef4444", fontWeight: 500 }}>
      {positive ? "" : "-"}{Math.abs(Math.round(value)).toLocaleString("en-GB")}
    </span>
  );
}

function OfficeNameRenderer({ value }) {
  const isFF = value === "Futures First";
  return (
    <span style={{ fontWeight: isFF ? 700 : 500, color: "#0f172a", fontSize: 12 }}>
      {isFF ? "Futures First — Total" : value}
    </span>
  );
}

function SectorNameRenderer({ value }) {
  const colour = SECTOR_COLOURS[value] ?? "#94a3b8";
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, pl: 2 }}>
      <Box sx={{ width: 8, height: 8, borderRadius: "50%", background: colour, flexShrink: 0 }} />
      <Typography sx={{ fontWeight: 600, color: "#0f172a", fontSize: 12 }}>{value}</Typography>
    </Box>
  );
}

function ProductNameRenderer({ value, data }) {
  // Subgroup header row — bold coloured label
  if (data?._rowType === "subgroup") {
    const colour = data._sectorColour ?? "#94a3b8";
    return (
      <span style={{
        color: colour, fontWeight: 700, fontSize: 10,
        letterSpacing: "0.06em", textTransform: "uppercase",
        paddingLeft: 16,
      }}>
        {value}
      </span>
    );
  }
  // Normal product row
  const colour = data?._sectorColour ?? "#94a3b8";
  return (
    <Box sx={{ pl: 4 }}>
      <span style={{ color: colour, marginRight: 6 }}>└</span>
      <span style={{ color: "#334155", fontSize: 11 }}>{value}</span>
      {data?.Asset_Class && (
        <span style={{ color: "#94a3b8", marginLeft: 6, fontSize: 10 }}>{data.Asset_Class}</span>
      )}
    </Box>
  );
}

// ─── Column builder ───────────────────────────────────────────────────────────

function buildColumns(varMode, nameRenderer, nameHeader = "Location", allowSort = true) {
  const varCurrent  = varMode === "100D" ? "VaR_100D"      : "VaR_10D";
  const varDelta    = varMode === "100D" ? "Delta_100D"    : "Delta_10D";
  const varDeltaT1  = varMode === "100D" ? "Delta_100D_t1" : "Delta_10D_t1";

  return [
    {
      field: "name",
      headerName: nameHeader,
      cellRenderer: nameRenderer,
      flex: 2, minWidth: 180, sortable: false,
      cellStyle: { display: "flex", alignItems: "center", justifyContent: "flex-start" },
    },
    {
      headerName: "VAR",
      children: [
        { field: varCurrent,  headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 90, type: "numericColumn", sortable: allowSort, ...(allowSort && { sort: "desc" }) },
        { field: varDelta,    headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90, type: "numericColumn", sortable: allowSort },
        { field: varDeltaT1,  headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90, type: "numericColumn", sortable: allowSort },
      ],
    },
    {
      headerName: "1D P&L",
      children: [
        { field: "_pnl1d", headerName: "Net P&L", cellRenderer: PnlRenderer, flex: 1, minWidth: 100, type: "numericColumn", sortable: allowSort },
      ],
    },
    {
      headerName: "5D P&L",
      children: [
        { field: "_pnl5d", headerName: "Cumulative", cellRenderer: PnlRenderer, flex: 1, minWidth: 100, type: "numericColumn", sortable: allowSort },
      ],
    },
    {
      headerName: "INIT. MARGIN",
      children: [
        { field: "Margin",          headerName: "Current", cellRenderer: NumRenderer,   flex: 1, minWidth: 100, type: "numericColumn", sortable: allowSort },
        { field: "Delta_Margin",    headerName: "Δ SOD",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: allowSort },
        { field: "Delta_Margin_t1", headerName: "Δ t-1",   cellRenderer: DeltaRenderer, flex: 1, minWidth: 90,  type: "numericColumn", sortable: allowSort },
      ],
    },
  ];
}

// ─── Shared grid defaults ─────────────────────────────────────────────────────

const DEFAULT_COL_DEF = {
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
  "--ag-cell-horizontal-padding":  "10px",
  "--ag-row-height":               "34px",
  "--ag-header-height":            "34px",
  "--ag-borders":                  "none",
  "--ag-row-border-style":         "solid",
  "--ag-row-border-width":         "1px",
  "--ag-row-border-color":         "#f1f5f9",
};

const PRODUCT_GRID_VARS = {
  ...GRID_VARS,
  "--ag-header-background-color":  "#f1f5f9",
  "--ag-font-size":                "11px",
  "--ag-row-height":               "30px",
  "--ag-header-height":            "30px",
  "--ag-row-border-color":         "#e9edf2",
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

// ─── Main component ───────────────────────────────────────────────────────────

export default function LocationTableAG({
  location, refreshKey,
  onOfficeClick, onSectorClick, onProductClick,
  simple = false,
}) {
  const [locData,        setLocData]        = useState([]);
  const [locLoading,     setLocLoading]     = useState(true);
  const [locError,       setLocError]       = useState(null);
  const [selectedOffice, setSelectedOffice] = useState(null);
  const [sectorData,     setSectorData]     = useState([]);
  const [sectorLoading,  setSectorLoading]  = useState(false);
  const [sectorError,    setSectorError]    = useState(null);
  const [sectorApiLoc,   setSectorApiLoc]   = useState(null);
  const [expandedSector, setExpandedSector] = useState(null);
  const [productState,   setProductState]   = useState({});
  const [varMode,        setVarMode]        = useState("100D");

  // ── Load office data + HAWK P&L in parallel ───────────────────────────────
  useEffect(() => {
    setLocLoading(true); setLocError(null);
    setSelectedOffice(null); setSectorData([]);
    setExpandedSector(null); setProductState({});

    Promise.all([
      getLocationTable(location),
      getHawkOfficePnl(),
    ])
      .then(([locRes, hawkRes]) => {
        const varRows = locRes.data.data  || [];
        const pnlRows = hawkRes.data.data || [];

        // Build a lookup of Office → { PnL_1D, PnL_5D }
        const pnlMap = {};
        for (const row of pnlRows) {
          pnlMap[row.Office] = { _pnl1d: row.PnL_1D, _pnl5d: row.PnL_5D };
        }

        // Merge P&L into VaR rows by Office name
        const merged = varRows.map(row => ({
          ...row,
          name:   row.Office,
          _pnl1d: pnlMap[row.Office]?._pnl1d ?? null,
          _pnl5d: pnlMap[row.Office]?._pnl5d ?? null,
        }));

        setLocData(merged);
        setLocLoading(false);
      })
      .catch(e => { setLocError(e.message); setLocLoading(false); });
  }, [location, refreshKey]);

  // ── Office click ──────────────────────────────────────────────────────────
  const handleOfficeClick = useCallback((office) => {
    if (simple) return;
    if (onOfficeClick) onOfficeClick(office);
    if (selectedOffice === office) {
      setSelectedOffice(null); setSectorData([]);
      setExpandedSector(null); setProductState({});
      return;
    }
    setSelectedOffice(office);
    setSectorData([]); setSectorLoading(true); setSectorError(null);
    setExpandedSector(null); setProductState({});
    const apiLoc = office === "Futures First" ? "Total" : office;
    setSectorApiLoc(apiLoc);
    getAssetClassTableGrouped(apiLoc)
      .then(r => {
        setSectorData((r.data.data || []).map(row => ({ ...row, name: row.Sector })));
        setSectorLoading(false);
      })
      .catch(e => { setSectorError(e.message); setSectorLoading(false); });
  }, [simple, selectedOffice, onOfficeClick]);

  // ── Sector click ──────────────────────────────────────────────────────────
  const handleSectorClick = useCallback((sector) => {
    if (onSectorClick) onSectorClick(sector, selectedOffice);
    if (expandedSector === sector) { setExpandedSector(null); return; }
    setExpandedSector(sector);
    if (productState[sector]?.data) return;
    setProductState(prev => ({ ...prev, [sector]: { loading: true, error: null, data: null } }));
    getProductTableBySector(sectorApiLoc, sector)
      .then(r => {
        const colour = SECTOR_COLOURS[sector] ?? "#94a3b8";
        const rows = (r.data.data || []).map(row => ({
          ...row,
          name: row.Product,
          _sectorColour: colour,
        }));
        setProductState(prev => ({ ...prev, [sector]: { loading: false, error: null, data: rows } }));
      })
      .catch(e => setProductState(prev => ({ ...prev, [sector]: { loading: false, error: e.message, data: null } })));
  }, [selectedOffice, expandedSector, productState, sectorApiLoc, onSectorClick]);

  // ── Column defs ───────────────────────────────────────────────────────────
  const officeCols  = useMemo(() => buildColumns(varMode, OfficeNameRenderer,  "Location"), [varMode]);
  const sectorCols  = useMemo(() => buildColumns(varMode, SectorNameRenderer,  "Sector"),   [varMode]);
  const productCols = useMemo(() => buildColumns(varMode, ProductNameRenderer, "Product", false), [varMode]);

  // ── Row styles ────────────────────────────────────────────────────────────
  const officeRowStyle = useCallback(({ data }) => {
    const isFF       = data?.Office === "Futures First";
    const isSelected = data?.Office === selectedOffice;
    return {
      fontWeight:   isFF ? 700 : 400,
      borderLeft:   isSelected ? "3px solid #3b82f6" : "3px solid transparent",
      background:   isSelected ? "#eff6ff" : isFF ? "#f8fafc" : "#fff",
      borderBottom: isFF ? "2px solid #cbd5e1" : "1px solid #f1f5f9",
      cursor:       simple ? "default" : "pointer",
    };
  }, [selectedOffice, simple]);

  const sectorRowStyle = useCallback(({ data }) => {
    const colour     = SECTOR_COLOURS[data?.Sector] ?? "#94a3b8";
    const isExpanded = data?.Sector === expandedSector;
    return {
      borderLeft:   `3px solid ${colour}`,
      background:   isExpanded ? `${colour}18` : "#fff",
      borderBottom: "1px solid #f1f5f9",
      cursor:       "pointer",
    };
  }, [expandedSector]);

  const productRowStyle = useCallback(({ data }) => {
    const colour = data?._sectorColour ?? "#94a3b8";
    if (data?._rowType === "subgroup") {
      return {
        background:   `${colour}12`,
        borderLeft:   `3px solid ${colour}`,
        borderBottom: `1px solid ${colour}30`,
        cursor:       "default",
      };
    }
    return {
      borderLeft:   `3px solid ${colour}40`,
      background:   "#f8fafc",
      borderBottom: "1px solid #e9edf2",
      cursor:       "pointer",
    };
  }, []);

  // ── Section header ────────────────────────────────────────────────────────
  function SectionHeader({ title, subtitle, onClose }) {
    return (
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{title}</Typography>
          {subtitle && <Typography sx={{ fontSize: 11, color: "#64748b" }}>{subtitle}</Typography>}
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <VarToggle varMode={varMode} setVarMode={setVarMode} />
          <Typography sx={{ fontSize: 11, color: "#94a3b8" }}>Values in USD</Typography>
          {onClose && (
            <Typography onClick={onClose} sx={{ fontSize: 11, color: "#3b82f6", cursor: "pointer" }}>
              ✕ Close
            </Typography>
          )}
        </Box>
      </Box>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (locLoading) return <Box sx={{ p: 2.5, color: "#94a3b8", fontSize: 12 }}>Loading...</Box>;
  if (locError)   return <Box sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {locError}</Box>;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>

      {/* ── Level 1: Office grid ── */}
      <Card elevation={0} sx={{ borderRadius: 2, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
        <CardContent sx={{ p: "16px !important" }}>
          <SectionHeader title="Portfolio / Office" />
          <Box className="ag-theme-alpine" sx={{ width: "100%", ...GRID_VARS }}>
            <AgGridReact
              theme="legacy"
              rowData={locData}
              columnDefs={officeCols}
              defaultColDef={DEFAULT_COL_DEF}
              domLayout="autoHeight"
              getRowStyle={officeRowStyle}
              onRowClicked={({ data }) => !simple && handleOfficeClick(data.Office)}
              suppressCellFocus
              suppressHorizontalScroll
              headerHeight={34}
              groupHeaderHeight={28}
            />
          </Box>
        </CardContent>
      </Card>

      {/* ── Level 2: Sector grid ── */}
      {!simple && selectedOffice && (
        <Card elevation={0} sx={{ borderRadius: 2, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
          <CardContent sx={{ p: "16px !important" }}>
            <SectionHeader
              title="Sector Breakdown"
              subtitle={`· ${selectedOffice === "Futures First" ? "Futures First — Total" : selectedOffice}`}
              onClose={() => {
                setSelectedOffice(null); setSectorData([]);
                setExpandedSector(null); setProductState({});
                if (onOfficeClick) onOfficeClick("Futures First");
              }}
            />
            {sectorLoading && <Typography sx={{ p: 2, color: "#94a3b8", fontSize: 12 }}>Loading...</Typography>}
            {sectorError   && <Typography sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {sectorError}</Typography>}
            {!sectorLoading && !sectorError && sectorData.length > 0 && (
              <>
                <Box className="ag-theme-alpine" sx={{ width: "100%", ...GRID_VARS }}>
                  <AgGridReact
                    theme="legacy"
                    rowData={sectorData}
                    columnDefs={sectorCols}
                    defaultColDef={DEFAULT_COL_DEF}
                    domLayout="autoHeight"
                    getRowStyle={sectorRowStyle}
                    onRowClicked={({ data }) => handleSectorClick(data.Sector)}
                    suppressCellFocus
                    suppressHorizontalScroll
                    headerHeight={34}
                    groupHeaderHeight={28}
                  />
                </Box>

                {/* ── Level 3: Product grid ── */}
                {expandedSector && (() => {
                  const ps     = productState[expandedSector];
                  const colour = SECTOR_COLOURS[expandedSector] ?? "#94a3b8";
                  return (
                    <Box sx={{ mt: 1, borderLeft: `3px solid ${colour}`, pl: 1 }}>
                      {ps?.loading && <Typography sx={{ p: 1.5, color: "#94a3b8", fontSize: 12 }}>Loading products...</Typography>}
                      {ps?.error   && <Typography sx={{ p: 1.5, color: "#ef4444", fontSize: 12 }}>Error: {ps.error}</Typography>}
                      {ps?.data && ps.data.length === 0 && <Typography sx={{ p: 1.5, color: "#94a3b8", fontSize: 12 }}>No product data available.</Typography>}
                      {ps?.data && ps.data.length > 0 && (
                        <Box className="ag-theme-alpine" sx={{ width: "100%", ...PRODUCT_GRID_VARS }}>
                          <AgGridReact
                            theme="legacy"
                            rowData={ps.data}
                            columnDefs={productCols}
                            defaultColDef={DEFAULT_COL_DEF}
                            domLayout="autoHeight"
                            getRowStyle={productRowStyle}
                            onRowClicked={({ data }) => {
                              if (data?._rowType === "subgroup") return;
                              onProductClick && onProductClick(data.Product, selectedOffice);
                            }}
                            suppressCellFocus
                            suppressHorizontalScroll
                            headerHeight={30}
                            groupHeaderHeight={24}
                          />
                        </Box>
                      )}
                    </Box>
                  );
                })()}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
