---
name: stock-crash-analyzer
description: |
  Analyze stock crash events and generate interactive HTML reports. This skill should be used when the user wants to analyze a stock's historical price drops, understand recovery patterns, identify whether crashes are stock-specific or market-driven, or generate investment statistics for crash events. Triggers include: "analyze stock crashes", "stock drop analysis", "暴跌分析", "crash recovery stats", or any request to analyze historical price declines, drawdowns, or recovery patterns for a specific stock.
agent_created: true
---

# Stock Crash Analyzer

Analyze historical stock price drops and generate interactive HTML reports with recovery statistics, cause classification, and investment insights.

## When to Use This Skill

This skill should be used when:
- The user wants to analyze a stock's historical crash events (daily drops > threshold)
- The user asks for recovery statistics, bounce probabilities, or repair-day analysis
- The user wants to know if a crash is stock-specific or market-driven
- The user wants to compare a stock's behavior against a benchmark index during drops
- The user asks for investment statistics like "V-shape recovery rate", "post-crash 5-day returns", or "median recovery days"
- The user asks in Chinese: "分析XX暴跌", "XX跌了多少", "XX修复天数", etc.

## Workflow

### Step 1: Determine Parameters

Gather the following from the user or use defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--stock` | (required) | Target stock symbol (e.g., AAPL, TSLA, NVDA, 000001) |
| `--benchmark` | QQQ | Benchmark index for comparison (e.g., QQQ, SPY, IXIC, 上证指数) |
| `--start` | (required) | Start date (YYYY-MM-DD) |
| `--end` | (required) | End date (YYYY-MM-DD) |
| `--threshold` | 2.0 | Drop threshold percentage (default: 2.0% for US stocks, 1.5% for low-volatility stocks) |
| `--output` | (required) | Output HTML file path |
| `--events` | (optional) | External events JSON file for detailed event descriptions |

### Step 2: Run the Analysis Script

Execute the analysis script with determined parameters:

```bash
python ~/.workbuddy/skills/stock-crash-analyzer/scripts/analyze_crashes.py \
  --stock AAPL \
  --benchmark QQQ \
  --start 2021-01-01 \
  --end 2026-06-26 \
  --threshold 2.0 \
  --output /path/to/report.html
```

The script will:
1. Fetch daily K-line data for both the stock and benchmark (via westock-data or yfinance fallback)
2. Calculate daily returns and identify all drops > threshold
3. Classify each drop cause (stock-specific vs market-driven)
4. Calculate recovery days (days to close above pre-drop level)
5. Compute 5-day post-crash returns, next rally, and all statistics
6. Generate an interactive HTML report with SVG charts, filterable tables, and investment insights

### Step 3: Handle Missing Events (Optional)

If the user wants detailed event descriptions for each crash:

1. Create a JSON file with date -> event mapping:
   ```json
   {
     "2025-03-11": "Bloomberg reports Apple delays Siri AI upgrade",
     "2026-06-25": "Apple announces product price increases across all lines"
   }
   ```
2. Pass the file path with `--events /path/to/events.json`

If no events file is provided, the script auto-generates generic descriptions based on cause classification.

### Step 4: Present the Report

After generation, present the HTML file to the user using `present_files`. The report is self-contained with no external dependencies.

## Cause Classification Logic

The script automatically classifies each crash into three categories based on the benchmark's performance on the same day:

| Cause | Benchmark Condition | Interpretation |
|-------|---------------------|----------------|
| **自身导致** (Stock-specific) | Benchmark >= -0.3% | Market is stable or up, stock drops alone |
| **整体下挫** (Market-driven) | Benchmark < -1.5% | Broad market crash, stock follows |
| **整体偏空+自身弱** (Mixed) | -1.5% <= Benchmark < -0.3% | Market is weak, stock drops more than market |

## Key Statistics Computed

The report includes these investment-focused statistics:

- **Median recovery days**: More robust than mean, less affected by outliers
- **Recovery probability**: 2/3/5/7/10/30/60-day windows
- **V-shape recovery rate**: % of crashes that recover within 5 days
- **Drop-tier analysis**: Recovery stats broken down by drop magnitude (2-3%, 3-4%, 4-5%, >5%)
- **Monthly distribution**: Seasonal patterns of crashes
- **Post-crash 5-day average return**: Mean reversion indicator
- **5-day positive probability**: Likelihood of being green after 5 days
- **Bounce magnitude**: Average gain on the recovery day
- **Self vs Market gap**: Difference in recovery speed between stock-specific and market-driven crashes

## Report Features

The generated HTML report includes:
- Fixed left sidebar with navigation links
- Interactive SVG charts (no external CDN dependencies)
- Filterable tables with multi-select cause filtering and keyword search
- Sortable columns (click headers for ascending/descending)
- Apple Design-inspired color scheme (green for up, red for down)
- Responsive layout for mobile and desktop

## Threshold Recommendations

| Stock Type | Suggested Threshold | Rationale |
|------------|---------------------|-----------|
| Mega-cap tech (AAPL, MSFT) | 2.0% | Moderate volatility |
| High-beta tech (TSLA, NVDA) | 3.0-4.0% | Higher normal volatility |
| Low-volatility (JNJ, PG) | 1.5% | Lower normal volatility |
| A-shares (China) | 2.0-3.0% | Higher circuit-breaker sensitivity |

## Methodology Reference

For detailed analysis methodology, see `references/methodology.md`.
