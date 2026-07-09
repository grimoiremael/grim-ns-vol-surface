# Grim--NS Volatility Surface Model Architecture

## 1. Architectural thesis

The Grim--NS Volatility Surface Model is a Python-centered volatility research engine with multiple possible workbench surfaces. It should not be architected as a spreadsheet model, a Bloomberg-only tool, a broker plugin, or a visualization script. The central object is a disciplined computation pipeline that transforms noisy options-chain data into auditable implied-volatility observations and, later, surface estimates and strategy overlays.

The first working version should be deliberately modest. A small, inspectable Toy Model is preferred over a visually impressive but epistemically fragile surface.

## 2. Canonical pipeline

The system is governed by the following abstract pipeline:

```text
RawChain -> NormalizedChain -> AdmissibleQuoteSet -> IVPointSet -> SurfaceEstimate -> RenderLayer -> StrategyOverlay
```

Each stage has a distinct responsibility.

### RawChain

RawChain is the vendor- or file-shaped input. It may come from CSV, XLSX, Bloomberg, another API, or synthetic fixtures. RawChain is not trusted.

### NormalizedChain

NormalizedChain converts source-specific fields into the project schema. It standardizes strikes, expiries, bid, ask, last, volume, open interest, option type, quote timestamp, underlying symbol, spot, and source metadata.

### AdmissibleQuoteSet

AdmissibleQuoteSet applies quote-quality rules and assigns acceptance, rejection, or warning states. It must preserve reason codes rather than silently discarding all context.

### IVPointSet

IVPointSet contains computed implied-volatility observations. Ideally this includes bid IV, mid IV, ask IV, solver status, moneyness, time to expiry, and the quote-quality state that produced the point.

### SurfaceEstimate

SurfaceEstimate is the estimated volatility object derived from IV points. In early versions this may be merely a set of expiry smiles or an ATM term structure. Full interpolation, smoothing, and no-arbitrage treatment are deferred.

### RenderLayer

RenderLayer consumes structured output objects and produces plots, tables, JSON, XLSX files, or static HTML reports. Rendering must not recompute pricing or admissibility logic.

### StrategyOverlay

StrategyOverlay is a downstream research feature that places option structures on top of the surface or smile representation. It should show where a structure buys volatility, sells volatility, crosses term structure, or relies on skew.

## 3. Workbench and deployment philosophy

The system must support multiple operator workbenches. Nervous Structure's workflow appears phone-heavy, spreadsheet-friendly, and travel-constrained. Other users may choose different workbenches and data pipes. Therefore the backend/core must not assume a single display layer.

The backend is responsible for:

- ingesting option-chain data through adapters;
- normalizing that data;
- applying admissibility filters;
- computing implied volatility;
- producing smiles, term structures, heatmaps, and later surfaces;
- returning structured outputs with confidence and rejection metadata.

The frontend/workbench is responsible for:

- displaying results;
- allowing simple parameter modification;
- presenting diagnostics;
- exporting reports;
- remaining usable from a phone where possible.

Spreadsheets are workbench surfaces, not computational authority. Excel/XLSX files may be used for input, output, and operator review, but the core calculations should remain in Python and be independently tested.

The intended interface family is:

```text
Python Core Engine
    -> Backend/API boundary, later
        -> Excel/XLSX workbench
        -> JSON output
        -> Static HTML/mobile report
        -> Future web dashboard
```

## 4. Data-source adapter philosophy

Data-source adapters convert external formats into NormalizedChain. They must not own the pricing engine.

Planned adapters:

- `CSVChainSource`: early local fixture ingestion.
- `XLSXChainSource`: early spreadsheet-compatible ingestion.
- `BloombergChainSource`: deferred; later adapter only.
- `OtherAPISource`: deferred; generic external data adapter.

Bloomberg is potentially authoritative and valuable, but the Toy Model must not depend on a Bloomberg session. The engine must be testable without proprietary data, live entitlements, or network access.

## 5. Package layout

The intended repository layout is:

```text
grim-ns-vol-surface/
  AGENTS.md
  README.md
  pyproject.toml
  .gitignore
  .env.example

  docs/
    architecture.md
    vol_surface_spec.tex
    vol_surface_spec.pdf

  src/
    volsurface/
      __init__.py
      core/
        schema.py
        cleaning.py
        forwards.py
        bsm.py
        iv_solver.py
        surface.py
      data_sources/
        csv_source.py
        xlsx_source.py
        bloomberg_source.py
      api/
        server.py
        routes.py
      workbench/
        excel_export.py
        html_report.py
        json_export.py

  tests/
    test_schema.py
    test_cleaning.py
    test_forwards.py
    test_bsm.py
    test_iv_solver.py

  examples/
    sample_chain_synthetic.csv

  outputs/
    .gitkeep
```

Some files are intentionally deferred and may begin as stubs or not exist until explicitly implemented.

## 6. Core domain objects

The following objects should be treated as early schema candidates. Exact fields may evolve, but changes must be tested and documented.

### OptionQuote

Represents the raw or minimally parsed quote from a source.

Candidate fields:

- `symbol`
- `underlying`
- `expiry`
- `strike`
- `option_type`
- `bid`
- `ask`
- `last`
- `volume`
- `open_interest`
- `quote_timestamp`
- `source`

### NormalizedOptionQuote

Represents a quote after normalization and basic type conversion.

Additional candidate fields:

- `spot`
- `rate`
- `dividend_yield`
- `time_to_expiry`
- `mid`
- `forward`
- `log_moneyness`

### AdmissibilityFlag

Represents a warning or rejection reason.

Initial reason-code set:

- `ZERO_MARKET`
- `WIDE_SPREAD`
- `STALE_QUOTE`
- `LOW_MID`
- `BOUND_VIOLATION`
- `PARITY_VIOLATION`
- `IV_OUT_OF_RANGE`
- `LOW_LIQUIDITY`

### IVPoint

Represents the result of IV computation.

Candidate fields:

- `quote_id`
- `underlying`
- `expiry`
- `strike`
- `option_type`
- `time_to_expiry`
- `forward`
- `log_moneyness`
- `iv_bid`
- `iv_mid`
- `iv_ask`
- `solver_status`
- `admissibility_status`
- `admissibility_flags`

## 7. Mathematical conventions

The first implementation uses Black--Scholes--Merton with continuous dividend yield.

Midpoint:

```text
mid = (bid + ask) / 2
```

Forward estimate:

```text
F = S * exp((r - q) * T)
```

Moneyness:

```text
log_moneyness = log(K / F)
```

Implied volatility is recovered by solving:

```text
market_price = BSM(S, K, T, r, q, sigma)
```

for `sigma`.

Preferred solver: Brent's method or another bracketing method with structured failure states.

Newton-only inversion is disfavored for the early engine because vega can become tiny deep ITM, deep OTM, or close to expiry.

## 8. Version gates

### V0 / Toy Model

Manual CSV or XLSX input; normalized schema; Black--Scholes--Merton pricing; implied-volatility inversion; basic smile rendering. No live APIs. No Bloomberg dependency. No backend server. No strategy overlay.

### V1 / Clean Local MVP

CSV/XLSX ingestion; quote admissibility flags; bid/mid/ask IV where possible; ATM term structure; basic XLSX and static HTML reports. Synthetic fixtures and tests required.

### V2 / Research Instrument

Persistent storage; historical surfaces; skew metrics; term-structure metrics; strategy overlays; uncertainty bands; more operator diagnostics.

### V3 / Trading-grade Candidate

Stale-quote controls; put-call parity checks; no-arbitrage checks; smoothing/calibration layer; alerting; surface-difference tracking; robust failure reporting.

### V4 / Institutional-grade Direction

Full data normalization across vendors; corporate actions; dividends; rates; advanced calibration; historical backtesting; entitlement-aware Bloomberg adapter; production deployment.

## 9. Deferred work

The following are explicitly deferred unless a task says otherwise:

- Bloomberg integration.
- Broker integration.
- Live API ingestion.
- Cloud deployment.
- Authentication.
- Automated trading.
- Black--76.
- SVI/SABR calibration.
- No-arbitrage smoothing.
- Historical backtesting.
- Strategy overlays.

Deferral is not rejection. It is sequencing discipline.

## 10. Initial build priority

The first implementation sequence should be:

1. Repository scaffold and package import.
2. Schema objects.
3. BSM pricing.
4. Forward and moneyness utilities.
5. IV solver with structured result.
6. Quote admissibility filters.
7. Synthetic CSV fixture ingestion.
8. Basic smile plot.
9. XLSX report export.
10. Static HTML report export.

Each task should be small enough to review as a single diff.

## 11. Non-goals

The project is not, in its early versions:

- a Bloomberg replacement;
- a broker execution system;
- a portfolio manager;
- a risk engine for live allocation;
- a mobile app;
- a web SaaS product;
- a spreadsheet-only calculator.

It is first an auditable volatility-surface research engine.
