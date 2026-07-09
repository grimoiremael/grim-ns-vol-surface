# AGENTS.md

## Project identity

This repository implements the Grim--NS Volatility Surface Model.

The project is currently in the Toy Model / V1.0 preparation stage. The intended early system is a local, testable Python engine that accepts manual or fixture-based option-chain input, normalizes quotes, applies admissibility logic, computes Black--Scholes--Merton implied volatility, and emits simple workbench outputs.

The long-term project target is a research instrument, not a decorative market-data renderer and not an automated trading system.

## Current version gate

Until explicitly instructed otherwise, work only toward the Toy Model / V1.0 boundary:

- CSV and XLSX fixture ingestion may be implemented.
- Synthetic sample data may be used.
- Normalized schemas may be implemented.
- Black--Scholes--Merton pricing may be implemented.
- Implied-volatility inversion may be implemented.
- Quote admissibility flags and rejection reasons may be implemented.
- Simple 2D smile, term-structure, XLSX, JSON, and static HTML outputs may be implemented.

Do not implement Bloomberg, broker, live API, cloud deployment, user authentication, execution, portfolio management, alerts, SVI/SABR calibration, no-arbitrage smoothing, or automated trading unless a task explicitly instructs that those items are in scope.

## Architectural invariants

Preserve the abstract pipeline:

```text
RawChain -> NormalizedChain -> AdmissibleQuoteSet -> IVPointSet -> SurfaceEstimate -> RenderLayer -> StrategyOverlay
```

The computational core must remain independent from any specific frontend, spreadsheet program, Bloomberg session, broker, desktop environment, or phone workflow.

The following separations are mandatory:

- Data-source adapters must not contain pricing or IV logic.
- Pricing and IV logic must not depend on rendering libraries.
- Rendering and workbench exports must consume structured result objects rather than recomputing core logic.
- Bloomberg, if later implemented, must be a data-source adapter, not the core engine.
- Excel/XLSX must be treated as an input/output and operator-review surface, not as the computational authority.
- Strategy overlays must be downstream of the surface/IV point objects, not entangled with quote cleaning.

## Data and licensing discipline

- Do not commit credentials, API keys, tokens, `.env` files, Bloomberg exports, broker exports, or proprietary market-data files.
- Use synthetic fixture data unless a task explicitly provides approved sample data.
- If a task mentions Bloomberg, assume the Bloomberg adapter is deferred unless the task explicitly says to implement a stub or interface.
- Do not infer entitlement or licensing rights from the mere existence of a data file.
- Generated outputs should normally stay under `outputs/` and should not be committed unless they are small, synthetic, and intentionally used as examples.

## Safety boundary

- Do not implement automated order placement.
- Do not implement broker login, broker execution, or trading automation.
- Do not include financial advice text in code comments, docs, or generated outputs.
- The system may support research, diagnostics, visualization, and operator review.
- Any future execution-related request must be treated as out of scope unless the repository architecture is explicitly revised by the owner.

## Engineering rules

- Prefer small, reviewable patches.
- Do not perform broad rewrites without explicit instruction.
- Do not change public schemas without updating tests and documentation.
- Do not introduce global mutable state for market data or calculation parameters.
- Prefer pure functions for pricing, inversion, forward estimation, and admissibility checks.
- Return structured result objects for failure-prone operations; do not let solver failures leak as unexplained exceptions into rendering or reports.
- Validate inputs at module boundaries.
- Keep error messages precise and operator-useful.

## Testing requirements

Before reporting completion, run the relevant test command. For ordinary Python changes, run:

```bash
pytest
```

If formatting or linting tools have been introduced, run them as well and report the result.

Required test posture:

- Pricing functions must have deterministic numerical tests.
- IV inversion must recover known volatility from model-generated prices.
- Admissibility filters must test accepted, rejected, and warning states.
- Workbench exports must be smoke-tested against synthetic data.
- Data-source adapters must be tested with local fixtures, not live services.

## Dependency discipline

- Keep dependencies modest.
- Do not add heavy frameworks unless the task explicitly calls for them.
- For the core engine, prefer `numpy`, `scipy`, and standard-library dataclasses or `pydantic` models only when useful.
- For XLSX workbench output, `openpyxl` is acceptable.
- For early rendering, `matplotlib` is acceptable.
- For a later API layer, `FastAPI` may be considered, but it is deferred by default.

## Documentation rules

- Update `docs/architecture.md` when module boundaries, pipeline stages, or version gates change.
- Keep `README.md` practical and operator-facing.
- Keep specifications in `docs/`.
- Do not bury architectural decisions inside comments only.
- If a task changes assumptions, record the assumption explicitly.

## Reporting format for completed tasks

When finishing a task, report:

1. Files changed.
2. What was implemented.
3. What was intentionally not implemented.
4. Tests run and their result.
5. Any blockers, uncertainties, or follow-up recommendations.

Do not claim success unless tests ran or there is a clear reason they could not run.

## Spreadsheet and mobile workflow

- Treat CSV/XLSX as first-class Toy Model interface formats.
- Do not move pricing, cleaning, IV inversion, or admissibility logic into spreadsheets.
- Keep spreadsheet handling in data-source or workbench modules.
- Prefer generated XLSX and static HTML outputs for operator review.
- Keep static HTML outputs mobile-readable where practical.
- Do not implement Bloomberg ingestion until the local CSV/XLSX engine passes tests.