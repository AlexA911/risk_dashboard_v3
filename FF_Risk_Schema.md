# FF_Risk Database Schema
**Server:** `it-ixe-sql-01.corp.hertshtengroup.com\TrackOrders`
**Database:** `FF_Risk`

---

## Lookup Tables

### dbo.Office
| Column | Type | Notes |
|--------|------|-------|
| OfficeId | INT IDENTITY PK | |
| OfficeName | VARCHAR(50) | |
| Region | VARCHAR(50) | |
| IsExcluded | BIT | 1 = London P&C, Mumbai |

### dbo.AssetClass
| Column | Type | Notes |
|--------|------|-------|
| AssetClassId | INT IDENTITY PK | |
| AssetClassName | VARCHAR(100) | |

**Current asset classes:** NG, Oils - Crude, Oils - Refined, WTI, USD Rates, GBP Rates, EUR Rates, CAD Rates, AUD Rates, CHF Rates, Volatility Indices, Equity Indices, FX, Sugar, Cocoa, Coffee, Grains, Live Stock, Metal Base, Metal Precious, Crypto, Dairy, Cotton

### dbo.ProductAssetClass
| Column | Type | Notes |
|--------|------|-------|
| ProductId | INT IDENTITY PK | |
| Product | VARCHAR(100) | UNIQUE INDEX |
| Asset_Class | VARCHAR(100) | |
| Exchange | VARCHAR(50) | |
| Notes | VARCHAR(200) | |

117 products mapped. Source of truth for product → asset class mapping.

---

## Risk Tables

### dbo.OfficeRisk
| Column | Type | Notes |
|--------|------|-------|
| Id | INT IDENTITY PK | |
| Date | DATE | |
| Time | TIME | 23:00 for EOD, actual time for intraday |
| Office | VARCHAR(50) | |
| Confidence | DECIMAL(5,2) | 95.00 or 100.00 |
| Lookback | INT | 100 or 10 |
| VaR | DECIMAL(18,4) | |
| Margin | DECIMAL(18,4) | |
| IsEOD | BIT | |
| CreatedAt | DATETIME | DEFAULT GETDATE() |

**Unique index:** Date + Time + Office + Confidence + Lookback

**Written by:** EOD script (both configs) + Intraday script (95/100 only)

---

### dbo.OfficeAssetClassRisk
| Column | Type | Notes |
|--------|------|-------|
| Id | INT IDENTITY PK | |
| Date | DATE | |
| Time | TIME | |
| Office | VARCHAR(50) | |
| Asset_Class | VARCHAR(100) | |
| Confidence | DECIMAL(5,2) | |
| Lookback | INT | |
| iVaR | DECIMAL(18,4) | Incremental VaR |
| Margin | DECIMAL(18,4) | |
| IsEOD | BIT | |
| CreatedAt | DATETIME | DEFAULT GETDATE() |

**Unique index:** Date + Time + Office + Asset_Class + Confidence + Lookback

**Written by:** Intraday script (from ivars_by_sector) — NOT YET IMPLEMENTED

---

### dbo.OfficeProductRisk
| Column | Type | Notes |
|--------|------|-------|
| Id | INT IDENTITY PK | |
| Date | DATE | |
| Time | TIME | |
| Office | VARCHAR(50) | |
| Asset_Class | VARCHAR(100) | Looked up from ProductAssetClass |
| Product | VARCHAR(100) | |
| Confidence | DECIMAL(5,2) | |
| Lookback | INT | |
| iVaR | DECIMAL(18,4) | |
| Margin | DECIMAL(18,4) | |
| IsEOD | BIT | |
| CreatedAt | DATETIME | DEFAULT GETDATE() |

**Unique index:** Date + Time + Office + Product + Confidence + Lookback

**Written by:** Intraday script (from ivars_by_contract) — NOT YET IMPLEMENTED

---

### dbo.AnalystRisk
| Column | Type | Notes |
|--------|------|-------|
| Id | INT IDENTITY PK | |
| Date | DATE | |
| Time | TIME | |
| Office | VARCHAR(50) | |
| Analyst | VARCHAR(100) | 3-letter code e.g. MRN |
| Confidence | DECIMAL(5,2) | |
| Lookback | INT | |
| VaR | DECIMAL(18,4) | |
| Margin | DECIMAL(18,4) | |
| IsEOD | BIT | |
| CreatedAt | DATETIME | DEFAULT GETDATE() |

**Unique index:** Date + Time + Office + Analyst + Confidence + Lookback

**Written by:** EOD script (both configs) + Intraday script (95/100 only)

---

### dbo.AnalystAssetClassRisk
| Column | Type | Notes |
|--------|------|-------|
| Id | INT IDENTITY PK | |
| Date | DATE | |
| Time | TIME | |
| Office | VARCHAR(50) | |
| Analyst | VARCHAR(100) | |
| Asset_Class | VARCHAR(100) | |
| Confidence | DECIMAL(5,2) | |
| Lookback | INT | |
| iVaR | DECIMAL(18,4) | |
| IsEOD | BIT | |
| CreatedAt | DATETIME | DEFAULT GETDATE() |

**Unique index:** Date + Time + Office + Analyst + Asset_Class + Confidence + Lookback

**Written by:** Intraday script (from ivars_by_sector) — NOT YET IMPLEMENTED

---

## Key Relationships

- `AnalystLookup_Margin_Data` (Market_Risk) used to resolve `account_code` → Office/Analyst
- Office rows: `Account = Office` in lookup
- Analyst rows: `Account != Office` in lookup
- `00000` / `0` = Futures First firm-wide netting group
- London P&C (9061) and Mumbai excluded from all writes

## Config Values
| Config | Confidence | Lookback |
|--------|-----------|---------|
| Primary | 95.00 | 100 |
| Secondary | 100.00 | 10 |

## EOD Snapshot
- Date rolls back to last trading day (Mon → Fri, otherwise D-1)
- Time = 23:00:00

## Intraday Snapshots
- Date = current date
- Time = actual run time
- Scheduled: 10:00, 11:00, 12:00, 13:00, 15:00, 17:00, 18:00, 18:30, 19:00, 19:30, 20:00, 20:30, 21:00, 21:30, 22:00, 22:30 (Mon-Fri)
- Only 95/100 config (no config loop in intraday script)

## Pending
- IT to grant `CORP\ostc.MarketRisk` db_datareader + db_datawriter on FF_Risk
- Add asset class and product writers to ff_risk_db.py (awaiting ivars column structure from 15:00 intraday log)
