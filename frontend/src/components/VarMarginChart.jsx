/**
 * VarMarginChart.jsx
 * Dual Y-axis line chart — VaR/iVaR (left) and Margin (right).
 * recharts — MUI wrapper.
 */
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getRollingChart, getSectorChart, getProductChart } from "../api/client";

function fmtM(val) {
  if (!val) return "0";
  return `$${(val / 1_000_000).toFixed(1)}M`;
}

function fmtAxis(val) {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(0)}M`;
  if (val >= 1_000)     return `$${(val / 1_000).toFixed(0)}K`;
  return val;
}

const TOGGLES = [
  { label: "5D",  days: 5  },
  { label: "1D",  days: 1  },
  { label: "1M",  days: 21 },
];

export default function VarMarginChart({ location, chartLabel, chartSector, chartProduct, onReset, refreshKey }) {
  const [period,  setPeriod]  = useState("5D");
  const [data,    setData]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const days = TOGGLES.find(t => t.label === period)?.days ?? 5;

  useEffect(() => {
    setLoading(true);
    setError(null);

    const merge = ([r10, r100], key10, key100) => {
      const map = {};
      r10.data.data.forEach(d => {
        map[d.Date] = { Date: d.Date, [key10]: d.iVaR ?? d.VaR, Margin: d.Margin };
      });
      r100.data.data.forEach(d => {
        if (map[d.Date]) {
          map[d.Date][key100] = d.iVaR ?? d.VaR;
          if (!map[d.Date].Margin) map[d.Date].Margin = d.Margin;
        } else {
          map[d.Date] = { Date: d.Date, [key100]: d.iVaR ?? d.VaR, Margin: d.Margin };
        }
      });
      return Object.values(map).sort((a, b) => String(a.Date).localeCompare(String(b.Date)));
    };

    const fetches = chartProduct
      ? [getProductChart(location, chartProduct, 100.0, 10, days), getProductChart(location, chartProduct, 95.0, 100, days)]
      : chartSector
      ? [getSectorChart(location, chartSector, 100.0, 10, days), getSectorChart(location, chartSector, 95.0, 100, days)]
      : [getRollingChart(location, 100.0, 10, days), getRollingChart(location, 95.0, 100, days)];

    Promise.all(fetches)
      .then(results => {
        const merged = merge(results, "VaR_10D", "VaR_100D");
        console.log("Chart data:", JSON.stringify(merged));
        setData(merged);
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });

  }, [location, chartSector, chartProduct, days, refreshKey]);

  const displayName  = chartLabel ?? (location === "Total" ? "Futures First — Total" : location);
  const isDrillDown  = !!(chartSector || chartProduct);
  const varLabel100  = isDrillDown ? "iVaR · 100D 95%" : "VaR · 100D 95%";
  const varLabel10   = isDrillDown ? "iVaR · 10D 100%" : "VaR · 10D 100%";
  const subtitleMode = chartProduct ? "Product iVaR contribution"
                     : chartSector  ? "Sector iVaR contribution"
                     : period === "1D" ? "Intraday snapshots"
                     : "EOD snapshots";

  const fmtX = (val) => {
    if (!val) return "";
    if (period === "1D") return val;
    const d = new Date(val);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  };

  const fmtLabel = (l) => {
    if (period === "1D") return l;
    const d = new Date(l);
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  };

  return (
    <Card elevation={0} sx={{ borderRadius: 2, boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
      <CardContent sx={{ p: "16px !important" }}>

        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>
              {displayName} · {period} Rolling
            </Typography>
            <Typography sx={{ fontSize: 11, color: "#94a3b8", mt: 0.25 }}>
              {subtitleMode} · {displayName}
            </Typography>
            {chartLabel && onReset && (
              <Typography onClick={onReset} sx={{ fontSize: 10, color: "#3b82f6", cursor: "pointer", mt: 0.25 }}>
                ← Back to firm-wide
              </Typography>
            )}
          </Box>

          <ToggleButtonGroup
            value={period} exclusive
            onChange={(_, val) => { if (val) setPeriod(val); }}
            size="small"
            sx={{
              "& .MuiToggleButton-root": {
                fontSize: 11, fontWeight: 600, padding: "2px 10px",
                border: "1px solid #e2e8f0", color: "#64748b", textTransform: "none",
                "&.Mui-selected": {
                  background: "#0f172a", color: "#fff", borderColor: "#0f172a",
                  "&:hover": { background: "#1e293b" },
                },
              },
            }}
          >
            {TOGGLES.map(t => (
              <ToggleButton key={t.label} value={t.label}>{t.label}</ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>

        {loading ? (
          <Typography sx={{ p: 5, textAlign: "center", color: "#94a3b8", fontSize: 12 }}>Loading chart...</Typography>
        ) : error ? (
          <Typography sx={{ p: 2, color: "#ef4444", fontSize: 12 }}>Error: {error}</Typography>
        ) : data.length === 0 ? (
          <Typography sx={{ p: 5, textAlign: "center", color: "#94a3b8", fontSize: 12 }}>No data available for this period.</Typography>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={data} margin={{ top: 4, right: 60, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="Date"
                tickFormatter={fmtX}
                tick={{ fontSize: 10, fill: "#64748b" }}
                interval="preserveStartEnd"
              />
              <YAxis
                yAxisId="var"
                tickFormatter={fmtAxis}
                tick={{ fontSize: 10, fill: "#64748b" }}
                width={56}
                domain={["auto", "auto"]}
                label={{ value: isDrillDown ? "iVaR" : "VaR", angle: -90, position: "insideLeft", fontSize: 10, fill: "#64748b" }}
              />
              <YAxis
                yAxisId="margin"
                orientation="right"
                tickFormatter={fmtAxis}
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                width={56}
                domain={["auto", "auto"]}
                label={{ value: "Margin", angle: 90, position: "insideRight", fontSize: 10, fill: "#94a3b8" }}
              />
              <Tooltip
                formatter={(val, name) => [fmtM(val), name]}
                labelFormatter={fmtLabel}
                contentStyle={{ fontSize: 11, borderRadius: 6 }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line yAxisId="var" type="monotone" dataKey="VaR_100D" name={varLabel100} stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              <Line yAxisId="var" type="monotone" dataKey="VaR_10D"  name={varLabel10}  stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4 2" dot={{ r: 3 }} connectNulls />
              <Line yAxisId="margin" type="monotone" dataKey="Margin" name="Initial Margin" stroke="#1e293b" strokeWidth={1.5} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
