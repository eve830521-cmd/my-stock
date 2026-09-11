# Calculation Specification (AI Code Generation Guide)

This document provides strict mathematical recipes and data processing rules for the My Stock Dashboard v3.0 to prevent AI hallucination or arbitrary assumption during code generation.

## 1. Dual Share Count System (Preventing Look-ahead Bias)
To accurately reflect historical valuations while maintaining a conservative stance on present absolute valuation:
* **Point-in-Time Diluted Shares**: Used strictly for historical charting (Phase 1, 2) and historical Valuation Bands (Chart 10, 11). This represents the actual shares outstanding at the end of that specific historical quarter. **Must be adjusted retroactively ONLY for stock splits / reverse splits**, not for capital increases (Rights Offerings, CB conversions).
* **Current Outstanding Shares**: The total outstanding shares as of the most recent trading day. Used exclusively for absolute valuation calculations like current S-RIM.

## 2. Normalized Operating EPS (정상화 영업 EPS)
* **Definition**: Designed to evaluate pure operating generation capability while reflecting real tax outflows and parent company ownership.
* **Formula**: `(Operating Profit * (1 - Effective Tax Rate)) * Controlling Interest Ratio / Point-in-Time Diluted Shares`
* **Note**: Do not deduct interest expense here to maintain focus on operating performance. Interest capacity is evaluated separately in the Financial Health chart.

## 3. Financial Health & Survival Metrics
* **Debt Ratio (부채비율)**: `Total Liabilities / Total Equity * 100`
* **Interest Coverage Ratio (이자보상배율)**: `Operating Profit / Interest Expense`
  - *Rule*: If Interest Expense is 0, return `N/A` or Infinity.
* **CAPEX / OCF Ratio**: `Capital Expenditures / Operating Cash Flow * 100`
  - *Rule*: If OCF is negative, return `N/A` rather than a misleading negative percentage.

## 4. DART Look-ahead Bias Prevention (Time-Alignment)
Historical quarterly/annual financial data MUST be matched with stock prices strictly AFTER the actual public release date.
* **Data Field**: Use OpenDART's `receipt_date` (or `receipt_datetime`).
* **Matching Rule**: If `receipt_datetime` is after market close (15:30 KST), the financial data becomes available for the valuation multiple on the *next* trading day. Hardcoding "May 15th" or "March 31st" is strictly prohibited.

## 5. Statistical Valuation Bands (Replacing ±1SD)
Because valuation multiples (PER, PBR) follow a right-skewed distribution, standard deviation (SD) is statistically invalid.
* **Metric**: Use non-parametric Percentiles based on a 10-year rolling window (or entire available history if less than 10 years).
* **Bands to Calculate**:
  - `Median (50th Percentile)`: The historical baseline.
  - `Buy Zone`: 10th Percentile (replaces -1SD).
  - `Sell Zone`: 90th Percentile (replaces +1SD).
* **Outlier & Negative Value Handling**: 
  - If earnings are negative, PER is mathematically `N/A`. Do not output negative PER.
  - Do not arbitrarily filter PER > 120 or PBR > 10. Percentile calculations natively filter out these extremes from skewing the `Median` or `10th/90th Percentiles`.

## 6. S-RIM (Sa Kyung-in's Residual Income Model) Parameters
To prevent the "Cyclical Trap" where peak earnings artificially inflate S-RIM value:
* **ROE Input**: Use the **10-Year Median ROE** (or Normalized ROE), NOT the TTM ROE.
* **Cost of Equity (Ke)**: Use the standard corporate bond yield (e.g., BBB- 5-year rate in Korea) as a baseline, dynamically fetched if possible, or defaulting to a conservative 8%.
* **Terminal Growth (w)**: Assume 0.9 (10% decay of excess return per year) or 1.0 (sustainable) depending on user toggle. Default to 0.9 for cyclical companies.
* **Formula**: `Intrinsic Value = Current Book Value + (Current Book Value * (10Y Median ROE - Ke)) / Ke` (Assuming w=1.0 for simplicity, adjust for w=0.9).

## 7. Contextual Tooltips (PBR Chart)
When hovering over a point in the PBR band, the tooltip MUST display:
1. Current PBR Value
2. The implied PBR Percentile (e.g., "Current PBR is at the 12th percentile of 10-year history")
3. `Current TTM ROE` vs `10-Year Median ROE`.
*This context immediately explains to the user if the stock is cheap due to a market panic (ROE is normal) or fundamental degradation (ROE has crashed).*
