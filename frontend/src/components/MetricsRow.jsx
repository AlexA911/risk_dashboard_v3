/**
 * MetricsRow.jsx
 * Top row of 5 metric cards — MUI v9
 * VaR 100D (K), VaR 10D (K), Initial Margin (M), Traded Vol (placeholder), Limit Utilisation (%)
 *
 * Limit Utilisation = Initial Margin / ($13,500,000 + CBOE VIX Margin)
 */
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { getMetrics, getVixMargin } from "../api/client";
import { LIMIT, calcUtilisation, utilisationColour } from "../utils/limitUtilisation";

function fmtK(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `$${Math.round(val / 1000).toLocaleString("en-GB")}K`;
}

function fmtM(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `$${(val / 1_000_000).toFixed(1)}M`;
}

function fmtPct(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function fmtChangeK(current, sod) {
  if (current == null || sod == null) return null;
  const delta = current - sod;
  const up = delta >= 0;
  return {
    text: `${up ? "▲" : "▼"} $${Math.abs(Math.round(delta / 1000)).toLocaleString("en-GB")}K from SOD`,
    up,
  };
}

function fmtChangeM(current, sod) {
  if (current == null || sod == null) return null;
  const delta = current - sod;
  const up = delta >= 0;
  return {
    text: `${up ? "▲" : "▼"} $${Math.abs(delta / 1_000_000).toFixed(1)}M from SOD`,
    up,
  };
}

function fmtChangePct(current, sod) {
  if (current == null || sod == null) return null;
  const delta = (current - sod) / LIMIT;
  const up = delta >= 0;
  return {
    text: `${up ? "▲" : "▼"} ${Math.abs(delta * 100).toFixed(1)}pp from SOD`,
    up,
  };
}


function MetricCard({ label, value, change, placeholder, valueColour, vixLabel }) {
  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 2,
        borderTop: "3px solid #3b82f6",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <CardContent sx={{ p: "14px 16px !important" }}>
        {/* Label */}
        <Typography sx={{
          fontSize: 11, fontWeight: 600, color: "#64748b",
          textTransform: "uppercase", letterSpacing: "0.05em", mb: 0.75,
        }}>
          {label}
        </Typography>

        {/* Value row */}
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.25, mb: 0.5 }}>
          <Typography sx={{
            fontSize: 24, fontWeight: 700,
            color: placeholder ? "#94a3b8" : (valueColour ?? "text.primary"),
          }}>
            {placeholder ? "—" : value}
          </Typography>
          {vixLabel && (
            <Typography sx={{ fontSize: 12, fontWeight: 700, color: "#64748b", whiteSpace: "nowrap" }}>
              {vixLabel}
            </Typography>
          )}
        </Box>

        {/* Delta */}
        {placeholder ? (
          <Typography sx={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
            Coming soon
          </Typography>
        ) : change ? (
          <Typography sx={{
            fontSize: 11, fontWeight: 500,
            color: change.up ? "#ef4444" : "#22c55e",
          }}>
            {change.text}
          </Typography>
        ) : (
          <Typography sx={{ fontSize: 11 }}>&nbsp;</Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default function MetricsRow({ location }) {
  const [data10,  setData10]  = useState(null);
  const [data100, setData100] = useState(null);
  const [vix,     setVix]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData10(null);
    setData100(null);
    setVix(null);
    Promise.all([
      getMetrics(location, 100.0, 10),
      getMetrics(location, 95.0, 100),
      getVixMargin(),
    ]).then(([r10, r100, rVix]) => {
      setData10(r10.data);
      setData100(r100.data);
      setVix(rVix);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [location]);

  const LABELS = ["VAR · 100D 95%", "VAR · 10D 100%", "INITIAL MARGIN", "TRADED VOLUME", "LIMIT UTILISATION"];

  if (loading || !data10 || !data100) {
    return (
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 1.5, mb: 2 }}>
        {LABELS.map(label => (
          <Card key={label} elevation={0} sx={{ borderRadius: 2, borderTop: "3px solid #3b82f6", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
            <CardContent sx={{ p: "14px 16px !important" }}>
              <Typography sx={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", mb: 0.75 }}>
                {label}
              </Typography>
              <Typography sx={{ fontSize: 24, fontWeight: 700, color: "#94a3b8" }}>—</Typography>
              <Typography sx={{ fontSize: 11 }}>&nbsp;</Typography>
            </CardContent>
          </Card>
        ))}
      </Box>
    );
  }

  const imCurrent    = data100.margin_current;
  const imSod        = data100.margin_sod;
  const vixCurrent   = vix?.vix_current ?? 0;
  const vixSod       = vix?.vix_sod     ?? 0;
  const utilRatio    = calcUtilisation(imCurrent, vixCurrent);
  const utilSod      = calcUtilisation(imSod, vixSod);

  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 1.5, mb: 2 }}>
      <MetricCard
        label="VAR · 100D 95%"
        value={fmtK(data100.var_current)}
        change={fmtChangeK(data100.var_current, data100.var_sod)}
      />
      <MetricCard
        label="VAR · 10D 100%"
        value={fmtK(data10.var_current)}
        change={fmtChangeK(data10.var_current, data10.var_sod)}
      />
      <MetricCard
        label="INITIAL MARGIN"
        value={fmtM(imCurrent)}
        change={fmtChangeM(imCurrent, imSod)}
      />
      <MetricCard label="TRADED VOLUME" placeholder />
      <MetricCard
        label="LIMIT UTILISATION"
        value={fmtPct(utilRatio)}
        change={fmtChangePct(utilRatio, utilSod)}
        valueColour={utilisationColour(utilRatio)}
        vixLabel={vixCurrent ? `VIX IM: ${fmtM(vixCurrent)}` : null}
      />
    </Box>
  );
}
