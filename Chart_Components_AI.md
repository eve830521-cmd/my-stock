# System Architecture & Logic Document: My Stock Dashboard v3.0

## 1. Core Investment Philosophy & Valuation Framework
This dashboard is engineered to systematize the investment philosophy of South Korean value investor Jung Chae-jin: **"Buy solid cyclical companies operating in South Korea during periods of extreme undervaluation, and scale out during periods of overvaluation."** 
It empirically tests a company's survivability and capital efficiency (Charts 1-9) before applying a rigid, statistically robust valuation framework (Charts 10-11) to determine the exact entry and exit points.

### Korean Market Specific Valuation Models
Unlike US equities where DCF (Discounted Cash Flow) and earnings-based PER models are highly effective due to steady free cash flows and high shareholder return yields, the South Korean equity market (KOSPI/KOSDAQ) is heavily skewed towards cyclical heavy-industries (semiconductors, chemicals, steel) with low dividend payout ratios. 

To overcome the "PER Trap" (where PER approaches infinity during a cyclical bottom as earnings drop to near zero), this dashboard explicitly champions and utilizes two valuation models optimized for the Korean market:
1. **Historical PBR Banding (Chart 11)**: During cyclical bottoms, operating cash flow may evaporate, but the underlying Book Value (BPS) remains highly resilient. Identifying the statistical absolute minimum (-1SD or Min band) of the 10-year PBR serves as the most reliable indicator of a cyclical bottom.
2. **S-RIM (Sa Kyung-in's Residual Income Model)**: Evaluates a firm's intrinsic value by anchoring on Book Value and adding the present value of future excess returns (ROE minus Cost of Equity). It effectively bypasses the volatility of Korean corporate cash flows.

---

## 2. Component Logic & Implementation Details

### Phase 1: Fundamental Viability & Survivability (Bottom-Cycle Stress Test)
**1. Revenue & Earnings Trend**
* **Source**: Raw quarterly/annual statements from DART (Financial Supervisory Service).
* **Rationale**: Filters out value traps by ensuring that despite cyclicality, the company exhibits a long-term upward trajectory in its peak-to-peak and trough-to-trough revenues and earnings.

**2. Profitability Margins (OP & NI Margin)**
* **Rationale**: Tests the company's economic moat. A resilient OP margin during a cyclical downturn proves the company has pricing power and will not face bankruptcy.

**3. Free Cash Flow (FCF)**
* **Calculation**: `Operating Cash Flow - CAPEX`
* **Rationale**: Confirms that actual cash is being deposited, preventing "흑자 부도" (profitable bankruptcy) and ensuring the firm has cash for down-cycle share buybacks or dividends.

**4. Financial Health (Debt-to-Equity Ratio)**
* **Rationale**: A strict filter to eliminate companies vulnerable to liquidity crises or forced capital raises (dilution) during periods of high interest rates and economic contractions.

### Phase 2: Shareholder Value & Capital Efficiency
**5. Return on Capital (ROE, ROA)**
* **Rationale**: The core driver of intrinsic value in S-RIM and the most critical metric for evaluating management's capital allocation efficiency in Korea.

**6. Normalized EPS & BPS (Strict Anti-Dilution Adjustment)**
* **Calculation**: `(Operating Profit * (1-Tax Rate) * Controlling Interest Ratio) / [Current Outstanding Shares]`
* **Rationale**: Korean markets are notorious for shareholder value destruction via frequent CB (Convertible Bond) issuances and rights offerings. To perfectly adjust for this dilution, the dashboard retroactively recalculates the entire 10-year historical EPS/BPS using ONLY the **most recent outstanding share count**, ensuring historical multiples are not artificially depressed.

**7. Dividends & Yield**
* **Rationale**: Acts as a safety margin to limit downside risk during prolonged bear markets.

**8. Outstanding Shares & Buybacks**
* **Rationale**: A direct monitoring system for capital dilution (share count increases) versus authentic shareholder returns (share cancellations).

**9. CAPEX to Operating Profit**
* **Rationale**: Verifies whether the company is adequately reinvesting its profits during downturns to capitalize on the next cyclical upswing.

### Phase 3: Timing and Valuation Execution
**10. PER Band (TTM / End-of-Week Close)**
* **Calculation**: `Weekly Friday Close Price / TTM Normalized EPS`
* **Outlier Control (Data Cleaning)**: If PER exceeds 120 (a mathematical anomaly due to near-zero earnings), the raw value is retained on the chart as a visual spike to inform the user of the historical event. However, it is **strictly excluded** from the rolling calculations of the Mean (Average) and Standard Deviations (+/- 1SD) to prevent the statistical baseline from being irreparably distorted.
* **Rationale**: Used during normal operating cycles to execute buys at historical extreme undervaluation (-1SD) and scale out at overvaluation (+1SD).

**11. PBR Band (TTM / End-of-Week Close) - The Core Cyclical Strategy**
* **Calculation**: `Weekly Friday Close Price / Latest Quarter BPS` (PBR > 10 excluded from Mean/SD).
* **Rationale**: The ultimate tool for Jung Chae-jin's philosophy. When earnings turn negative and PER is incalculable, PBR remains the solitary reliable anchor. The dashboard dynamically computes the **"Implied Price at -1SD"** based on current BPS, offering the user an exact, hard-coded target price for maximum safety margin entry.

---

## 3. Deep Dive & Rationality Analysis (Data Processing Robustness)

The dashboard's data processing logic goes beyond simple visualization templates. It is highly engineered to correct structural blind spots in the Korean stock market. The core rationale for its design is as follows:

### 3.1. Rationale for Separating TTM (Trailing Twelve Months) and Annual Data
* **The Problem with Annual Data**: Pure Annual data is perfect for evaluating long-term growth as it removes seasonality and presents clean, audited, year-end financials. However, for highly cyclical Korean industries (e.g., memory semiconductors, petrochemicals), industry conditions can reverse drastically within a single year. Waiting for an annual report means an investor will completely miss the cyclical bottom and subsequent price surge.
* **The TTM Solution**: By rolling the sum of the last 4 quarters, TTM inherently removes seasonality while capturing quarterly turnaround points in real-time. This allows the investor to spot the exact cyclical bottom and dynamically reflect it in the valuation bands without delay.

### 3.2. Suitability of Data Sources & Prevention of Look-Ahead Bias in TTM
* **Data Synergy**: Fundamental data is rigorously sourced from DART (official regulatory filings), while pricing data is sourced from FinanceDataReader at a high-resolution weekly (Friday close) frequency.
* **Elimination of Look-Ahead Bias**: The most common error in quantitative backtesting is look-ahead bias (using data before it was publicly available). For instance, Q1 earnings technically close on March 31st, but the regulatory filing deadline is May 15th. This dashboard's logic strictly enforces this lag: **Q1 earnings are only matched with stock prices from May 15th onwards.** Consequently, the historical valuation bands represent the *exact, 100% authentic valuations* that an investor would have calculated in real-time on any given past date.

### 3.3. Definition and Rationality of "Normalized EPS"
* **The Flaw of Standard EPS**: Standard EPS relies on Net Income, which in Korea is frequently polluted by non-operating noise (e.g., real estate sales, FX translation gains/losses, massive one-off impairment charges). Evaluating a cyclical company's core earning power based on this noisy metric is mathematically dangerous.
* **Normalized EPS Definition**: `(Operating Profit * (1 - Corporate Tax Rate)) * Controlling Interest Ratio / [Current Outstanding Shares]`
* **Rationality of the Application**:
  1. **Operating Profit Base**: Strips away all non-operating noise, isolating pure business generation capability.
  2. **Tax & Controlling Interest**: Taxes are hard cash outflows, and only the profit attributable to the parent company (Controlling Interest) represents true shareholder value.
  3. **Retroactive Adjustment using Current Shares**: By dividing the historical earnings by the **current** outstanding share count rather than the historical share count, the dashboard preemptively penalizes the historical EPS for all equity dilution (rights offerings, CB conversions) that occurred over the last 10 years. 
  
This three-step normalization process yields the most conservative, robust, and rational baseline for evaluating Korean equities.
