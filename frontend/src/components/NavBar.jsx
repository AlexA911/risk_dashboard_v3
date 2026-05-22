/**
 * NavBar.jsx
 * Top navigation bar — MUI v9
 */
import { useState, useEffect } from "react";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Chip from "@mui/material/Chip";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { getLocations } from "../api/client";

const NAV_ITEMS = [
  "Summary",
  "Summary - New",
  "Location",
  "Analyst",
  "Positions",
  "Stress",
  "Reports",
];

const ASSET_CLASSES = [
  "All Asset Classes",
  "Oils", "Oils - Crude", "Oils - Refined", "WTI", "NG",
  "Volatility Indices", "Equity Indices",
  "Cocoa", "Coffee", "Sugar", "Grains", "Live Stock", "Dairy", "Cotton",
  "Metal Base", "Metal Precious", "Crypto",
  "GBP Rates", "EUR Rates", "USD Rates", "CAD Rates", "AUD Rates", "CHF Rates",
  "FX",
];

const selectSx = {
  color: "#e2e8f0",
  fontSize: 12,
  height: 30,
  ".MuiOutlinedInput-notchedOutline": { borderColor: "#3d4460" },
  "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "#5a6380" },
  "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: "#3b82f6" },
  ".MuiSvgIcon-root": { color: "#64748b" },
  background: "#2d3347",
  borderRadius: 1,
};

const menuPropsSx = {
  PaperProps: {
    sx: {
      background: "#1e2436",
      border: "1px solid #3d4460",
      color: "#e2e8f0",
      fontSize: 12,
      "& .MuiMenuItem-root": {
        fontSize: 12,
        "&:hover":          { background: "#2d3347" },
        "&.Mui-selected":   { background: "#2d3347" },
      },
    },
  },
};

export default function NavBar({
  activePage, onPageChange,
  location, onLocationChange,
  assetClass, onAssetClassChange,
  dataAsOf,
}) {
  const [locations, setLocations] = useState(["Total"]);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    getLocations()
      .then(r => setLocations(["Total", ...r.data.locations]))
      .catch(() => setLocations(["Total"]));
  }, []);

  const timeStr = now.toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

  const asOfStr = dataAsOf ?? "--:--";
  const activeIndex = NAV_ITEMS.indexOf(activePage);

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        background: "#1a1f2e",
        borderBottom: "1px solid #2d3347",
        zIndex: 100,
      }}
    >
      <Toolbar
        variant="dense"
        sx={{ minHeight: 48, height: 48, px: "20px !important", gap: 0 }}
      >
        {/* Brand */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mr: 3.5, whiteSpace: "nowrap" }}>
          <Chip
            label="RISK"
            size="small"
            sx={{
              background: "#e74c3c",
              color: "#fff",
              fontWeight: 800,
              fontSize: 11,
              letterSpacing: "0.08em",
              height: 20,
              borderRadius: 1,
              "& .MuiChip-label": { px: "6px" },
            }}
          />
          <Typography sx={{ color: "#94a3b8", fontSize: 11, fontWeight: 400 }}>
            Futures First
          </Typography>
        </Box>

        {/* Tabs */}
        <Tabs
          value={activeIndex >= 0 ? activeIndex : 0}
          onChange={(_, i) => onPageChange(NAV_ITEMS[i])}
          sx={{
            flex: 1,
            minHeight: 48,
            "& .MuiTabs-indicator":  { background: "#3b82f6", height: 2 },
            "& .MuiTab-root": {
              color:       "#94a3b8",
              fontSize:    12,
              fontWeight:  400,
              minHeight:   48,
              padding:     "0 14px",
              textTransform: "none",
              whiteSpace:  "nowrap",
              "&.Mui-selected": { color: "#fff", fontWeight: 600 },
            },
          }}
        >
          {NAV_ITEMS.map(item => (
            <Tab
              key={item}
              label={
                item === "Summary - New" ? (
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.6 }}>
                    {item}
                    <Chip
                      label="NEW"
                      size="small"
                      sx={{
                        background: "#16a34a",
                        color: "#fff",
                        fontWeight: 700,
                        fontSize: 9,
                        letterSpacing: "0.04em",
                        height: 16,
                        borderRadius: 0.5,
                        "& .MuiChip-label": { px: "4px" },
                      }}
                    />
                  </Box>
                ) : item
              }
            />
          ))}
        </Tabs>

        {/* Right controls */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, ml: "auto" }}>
          {/* Data as-of */}
          <Typography sx={{ color: "#64748b", fontSize: 11, whiteSpace: "nowrap" }}>
            Data as of {asOfStr}
          </Typography>

          {/* Location dropdown */}
          <Select
            value={location}
            onChange={e => onLocationChange(e.target.value)}
            size="small"
            sx={selectSx}
            MenuProps={menuPropsSx}
          >
            {locations.map(l => (
              <MenuItem key={l} value={l}>
                {l === "Total" ? "Futures First" : l}
              </MenuItem>
            ))}
          </Select>

          {/* Asset class dropdown */}
          <Select
            value={assetClass}
            onChange={e => onAssetClassChange(e.target.value)}
            size="small"
            sx={selectSx}
            MenuProps={menuPropsSx}
          >
            {ASSET_CLASSES.map(ac => (
              <MenuItem key={ac} value={ac}>{ac}</MenuItem>
            ))}
          </Select>

          {/* Live clock */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, whiteSpace: "nowrap" }}>
            <Box sx={{
              width: 6, height: 6, borderRadius: "50%",
              background: "#22c55e",
              boxShadow: "0 0 4px #22c55e",
            }} />
            <Typography sx={{ color: "#22c55e", fontSize: 11, fontFamily: "monospace" }}>
              Live · {timeStr} BST
            </Typography>
          </Box>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
