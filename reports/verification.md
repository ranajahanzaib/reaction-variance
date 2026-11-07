# Local verification — 2026-11-02

- Exact source SHA-256: `bef283c5a5cd746d62b86fe97c0924686d9fc3580d05453015fe935bc3c2a531`.
- Successful repeated atomic imports: 50,688 records, four stable strict groups, 50,668 valid yields, 20 flagged values, no duplicate IDs.
- `make test`: 32 Python tests and two Vitest/React Testing Library tests passed.
- `make build`: TypeScript checking and Vite production build passed. Chart code is split into a separate cached bundle.
- `ruff check backend scripts`: passed.
- `make e2e`: two actual-data workflows passed on desktop and mobile against Vite.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8011 pnpm --dir frontend e2e`: both workflows passed against the production frontend served by FastAPI.
- Browser workflows block nonlocal requests and verify group switching, filtering, empty results, selection, difference classifications, CSV contents, responsive width, and absence of runtime page errors.
- Automated axe WCAG A/AA checks passed on the explored comparison and methodology states on both viewports. These checks are not a claim of exhaustive accessibility certification.
- `scripts/verify-example.py` reread both documented example records directly from the source with ORD's supported `DatasetView.get_reaction` API; confirmed the catalyst contrast and 99.18171 percentage-point difference.
- Genuine screenshots were captured from the application, including the production build; see `docs/`.
- `git diff --check`: passed. `PLAN.md` was not edited.

Python's test client emits a dependency deprecation warning concerning httpx;
all assertions pass. CI is configured but no hosted run is claimed. This is
local functional and scientific-transformation validation, not external
validation of the underlying experimental measurements. Component amounts
retain original units; exact-unit equivalence beyond temperature/time remains
conservative. The dataset is one screen and observational comparisons do not
establish causation or independent replication.
