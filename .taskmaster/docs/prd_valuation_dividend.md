# PRD: Valuation PER Band Fix, Friday Resampling Confirmation, Safety Tab Dividend Chart, and Valuation Tab Dividend Yield Band

## Overview
This document specifies the requirements and technical design for 4 major enhancements in the My Stock Dashboard:
1. Fix right Y-axis stock price scale distortion in Valuation PER Band (e.g., Samsung Electronics scaling to 1,000,000 KRW instead of 350,000 KRW) without altering the fundamental intent of PER band analysis.
2. Confirm and document the weekly Friday ('W-FRI') resampling mechanism for band dates (explaining why 2026-09-25 appears on 2026-09-22).
3. Add an "Annual Dividend & Dividend Payout Ratio" chart to the Safety tab to evaluate dividend sustainability, payout trend, and whether high dividend yields are temporary.
4. Add a "Stock Price & Dividend Yield Band" chart to the Valuation tab with isolated scale safeguards, ensuring no distortion of stock price scales and no side effects on other charts.

## Tasks

### Task 1: Fix PER Band Right Y-Axis Scale Distortion & Verify Band Integrity
- Root Cause: In cyclical companies (e.g., Samsung Electronics), downturn EPS collapses (e.g. to 704 KRW in 2023) created historical PER outliers up to 120x, pushing the 90th percentile (PER_Plus1SD) to 44.18x. When earnings recovered in 2026 to 20,399 KRW, the converted target price reached 901,180 KRW. Because this invisible line was placed on yAxisIndex: 1, ECharts scaled the right axis to 1,000,000 KRW, squashing the actual 354,000 KRW stock price.
- Solution: Isolate converted target prices (상위/하위 10% 환산주가) onto a hidden axis (yAxisIndex: 2 or axis unlinked from scale calculation) so that the visible right Y-axis (yAxisIndex: 1) scales purely based on actual stock price ('price'). Tooltip maintains exact target price values.
- Integrity Check: Verify that this does not distort PER band evaluation intent, but rather eliminates visual distortion.

### Task 2: Validate Weekly Friday Resampling Mechanics ('W-FRI')
- Confirm that database.py uses `df.resample('W-FRI').last()` to group daily data into weekly Friday endpoints.
- Document the lifecycle: mid-week prices update daily into the current week's Friday slot (2026-09-25), finalizing on Friday close, before rolling over to next week's Friday (2026-10-02).

### Task 3: Add Annual Dividend and Payout Ratio Chart to Safety Tab
- Purpose: Check dividend consistency, payout ratio growth, and determine whether high dividend yields are sustainable or temporary.
- Data Source: Sheet4(Annual) contains '배당금', '당기순이익', '지배순이익', '현재주식수'.
- Calculations: `배당성향(%) = (배당금 / 당기순이익) * 100`, `DPS(원) = 배당금 / 현재주식수`.
- Visualization: Left Y-axis = Total Dividend or DPS (Bar), Right Y-axis = Dividend Payout Ratio % (Line). Add modal explanation.

### Task 4: Add Stock Price & Dividend Yield Band to Valuation Tab
- Component: 12. 주가배당수익률 (Dividend Yield) 밴드.
- Formula: Dividend Yield = (DPS / Price) * 100. Safety margin target price = DPS / (Plus1SD / 100). Low dividend target price = DPS / (Minus1SD / 100).
- Scale Safeguard: Converted target prices placed on a hidden axis to avoid inflating the right Y-axis (preventing 70,000 KRW distortion for 50,000 KRW stock).
- Contrast: White dividend yield line, Neon green (#00ff00) stock price line, symbol: 'none'.
- Toolbar: Synchronized period buttons (6M, 12M, 24M, 36M, 60M, All) and dataZoom slider synchronization.
- Isolation: Purely self-contained without mutating or regressing other charts.
