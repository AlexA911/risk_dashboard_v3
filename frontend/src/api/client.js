import axios from "axios";

const BASE_URL = "http://localhost:8002";
const api = axios.create({ baseURL: BASE_URL });

export const getLocations                = ()                                              => api.get("/api/locations");
export const getAssetClasses             = ()                                              => api.get("/api/asset-classes");
export const getMetrics                  = (location, confidence, lookback)                => api.get("/api/metrics",                   { params: { location, confidence, lookback } });
export const getRollingChart             = (location, confidence, lookback, days)          => api.get("/api/rolling-chart",             { params: { location, confidence, lookback, days } });
export const getLocationTable            = (location)                                      => api.get("/api/location-table",            { params: { location } });
export const getSectorChart              = (location, sector, confidence, lookback, days)  => api.get("/api/sector-chart",              { params: { location, sector, confidence, lookback, days } });
export const getVixMargin                = ()                                              => fetch(`${BASE_URL}/api/vix-margin`).then(r => r.json());
export const getProductChart             = (location, product, confidence, lookback, days) => api.get("/api/product-chart",             { params: { location, product, confidence, lookback, days } });
export const getLastSnapshot             = ()                                              => fetch(`${BASE_URL}/api/last-snapshot`).then(r => r.json());
export const getAssetClassTableGrouped   = (location)                                      => api.get("/api/asset-class-table-grouped", { params: { location } });
export const getProductTableBySector     = (location, sector)                              => api.get("/api/product-table-by-sector",  { params: { location, sector } });
export const clearCache                  = ()                                              => api.post("/api/cache/clear");