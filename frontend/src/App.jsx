/**
 * App.jsx — Root component with page routing.
 *
 * Polling strategy: instead of a fixed 5-minute timer, we check every minute
 * whether the current time has just passed one of the known intraday snapshot
 * times (plus a 90-second buffer for the script to finish writing). If so, we
 * clear the cache and trigger a refresh. This means the UI only re-fetches
 * when new data is actually expected.
 *
 * EOD snapshot (23:00) is handled the same way.
 * Outside market hours the dashboard simply shows the last available data.
 */
import { useState, useEffect, useCallback } from "react";
import NavBar from "./components/NavBar";
import MetricsRow from "./components/MetricsRow";
import VarMarginChart from "./components/VarMarginChart";
import SummaryTable from "./components/SummaryTable";
import AnalystTab from "./components/AnalystTab";
import RollRiskTab from "./components/RollRiskTab";
import "./index.css";
import { getLastSnapshot, clearCache } from "./api/client";

// Scheduled intraday snapshot times (HH:MM) — mirrors Windows Task Scheduler
const SNAPSHOT_TIMES = [
  "10:00", "11:00", "12:00", "13:00", "15:00",
  "17:00", "18:00", "18:30", "19:00", "19:30",
  "20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00",
];

// How long after the scheduled time before we expect data to be ready (ms)
const SCRIPT_BUFFER_MS = 90_000; // 90 seconds

// How often we check whether a snapshot window has passed (ms)
const POLL_INTERVAL_MS = 60_000; // 1 minute

function getScheduledRefreshTime(timeStr) {
  const [h, m] = timeStr.split(":").map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return new Date(d.getTime() + SCRIPT_BUFFER_MS);
}

export default function App() {
  const [activePage,    setActivePage]    = useState("Summary");
  const [location,      setLocation]      = useState("Total");
  const [assetClass,    setAssetClass]    = useState("All Asset Classes");
  const [refreshKey,    setRefreshKey]    = useState(0);
  const [dataAsOf,      setDataAsOf]      = useState(null);

  // Chart drill-down state
  const [chartLocation, setChartLocation] = useState("Total");
  const [chartLabel,    setChartLabel]    = useState(null);
  const [chartSector,   setChartSector]   = useState(null);
  const [chartProduct,  setChartProduct]  = useState(null);

  // Reset chart when navbar location changes
  useEffect(() => {
    setChartLocation(location === "Total" ? "Total" : location);
    setChartLabel(null);
    setChartSector(null);
    setChartProduct(null);
  }, [location]);

  const fetchSnapshotTime = useCallback(() => {
    getLastSnapshot()
      .then(r => { if (r.snapshot_time) setDataAsOf(r.snapshot_time); })
      .catch(() => {});
  }, []);

  useEffect(() => { fetchSnapshotTime(); }, [fetchSnapshotTime]);

  useEffect(() => {
    const triggered = new Set();
    const check = () => {
      const now = new Date();
      for (const t of SNAPSHOT_TIMES) {
        if (triggered.has(t)) continue;
        const refreshAt = getScheduledRefreshTime(t);
        if (now >= refreshAt && now < new Date(refreshAt.getTime() + POLL_INTERVAL_MS)) {
          triggered.add(t);
          clearCache().catch(() => {});
          setRefreshKey(k => k + 1);
          fetchSnapshotTime();
          break;
        }
      }
    };
    const timer = setInterval(check, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchSnapshotTime]);

  function handleOfficeClick(office) {
    const loc = office === "Futures First" ? "Total" : office;
    setChartLocation(loc);
    setChartLabel(office === "Futures First" ? "Futures First — Total" : office);
    setChartSector(null);
    setChartProduct(null);
  }

  function handleSectorClick(sector, office) {
    const loc = office === "Futures First" ? "Total" : office;
    setChartLocation(loc);
    setChartLabel(`${office === "Futures First" ? "FF" : office} · ${sector}`);
    setChartSector(sector);
    setChartProduct(null);
  }

  function handleProductClick(product, office) {
    const loc = office === "Futures First" ? "Total" : office;
    setChartLocation(loc);
    setChartLabel(product);
    setChartSector(null);
    setChartProduct(product);
  }

  function handleChartReset() {
    setChartLocation(location === "Total" ? "Total" : location);
    setChartLabel(null);
    setChartSector(null);
    setChartProduct(null);
  }

  const chart = (
    <div style={{ marginBottom: 16 }}>
      <VarMarginChart
        location={chartLocation}
        chartLabel={chartLabel}
        chartSector={chartSector}
        chartProduct={chartProduct}
        onReset={handleChartReset}
        refreshKey={refreshKey}
      />
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f0f2f5" }}>
      <NavBar
        activePage={activePage}  onPageChange={setActivePage}
        location={location}      onLocationChange={setLocation}
        assetClass={assetClass}  onAssetClassChange={setAssetClass}
        dataAsOf={dataAsOf}
      />

      <div style={{ padding: "16px 20px" }}>

        {/* ── Summary ── */}
        {activePage === "Summary" && (
          <>
            <MetricsRow location={location} refreshKey={refreshKey} />
            <SummaryTable
              location={location}
              refreshKey={refreshKey}
              onOfficeClick={handleOfficeClick}
              onSectorClick={handleSectorClick}
              onProductClick={handleProductClick}
              chartSlot={chart}
            />
          </>
        )}

        {/* ── Analyst tab ── */}
        {activePage === "Analyst" && (
          <AnalystTab location={location} refreshKey={refreshKey} />
        )}

        {/* ── Roll Risk tab ── */}
        {activePage === "Roll Risk" && (
          <RollRiskTab location={location} refreshKey={refreshKey} />
        )}

        {/* ── All other pages ── */}
        {!["Summary", "Summary - Old", "Analyst", "Roll Risk"].includes(activePage) && (
          <div style={{
            background: "#fff", borderRadius: 8, padding: 40,
            textAlign: "center", color: "#94a3b8", fontSize: 14,
            boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
          }}>
            {activePage} — coming soon
          </div>
        )}

      </div>
    </div>
  );
}
