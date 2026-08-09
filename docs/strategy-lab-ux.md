# Strategy Lab UX Direction

## Product Goal

Strategy Lab should feel like an interactive research canvas, not a four-part data-entry form. Users should spend most of their time expressing an idea, seeing how it behaves on a chart, and examining evidence. Ticker, costs, validation settings, and provider details remain available without dominating the primary workflow.

## Release 0.4.3 Status

The first complete React vertical slice now implements this direction:

- Vite, React, TypeScript, Tailwind, and editable shadcn/ui components live under `app/web/`.
- Command search combines validated templates, saved catalogue strategies, and natural-language entry.
- A single reducer makes instruction, template, and catalogue selections mutually exclusive.
- Rule parameters are editable chips inside readable sentences; search ranges stay inside each chip popover.
- Test assumptions use a side sheet and default to zero commission and slippage.
- The market chart remains visible before and after research and updates rule overlays immediately.
- Wide screens support correctly constrained percentage resizing plus a persistent stacked-layout alternative; narrow screens stack automatically.
- Evidence uses tabs for overview, equity/drawdown, trades, robustness, and assumptions.
- Natural-language translation requires a readable confirmation step and hides YAML from the common path.
- FastAPI serves the React build when available and retains `/legacy` during panel-by-panel migration.

At the 0.4.3 release boundary, Option Lab, Stock Observatory, and Market Pulse remained in the vanilla fallback. Release 0.5 ports Option Lab; Stock Observatory and Market Pulse still require functional parity before the fallback can be retired.

## Recommended Experience

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ NVDA  ·  1 Year  ·  SMA Crossover                         Run Research →    │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ Strategy Composer             │ Live Market Preview                         │
│                               │                                             │
│ “Long when [SMA 10] crosses   │ Candles + volume + SMA 10 / SMA 50          │
│  above [SMA 50] …”            │ Entry/exit markers and crosshair details     │
│                               │                                             │
│ + Add Filter  + Add Exit      │                                             │
│ Risk ▾  Search Range ▾        │                                             │
├───────────────────────────────┴─────────────────────────────────────────────┤
│ Overview | Equity & Drawdown | Trades | Robustness | Assumptions            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Start And Select

- Use one prominent natural-language composer with suggested prompts.
- Open templates and saved strategies through a searchable command palette rather than a permanent select input.
- Display recent strategies and family cards as quick starts.
- Keep ticker and timeframe in a compact research context bar shared by the chart and run action.

### Configure By Editing A Sentence

- Render rules as readable clauses with interactive parameter chips: `SMA 10`, `crosses above`, `SMA 50`, `stop 5%`.
- Open a small popover or slider when a value chip is selected.
- Add filters, exits, and risk controls through contextual actions instead of showing every possible field.
- Show the generated rule graph only in an Advanced view.

### Design The Test Through Progressive Disclosure

- Keep defaults visible as a compact summary: `SPY · 0 bps · Next Open · 1 Year`.
- Move commission, slippage, validation split, benchmark overrides, and automatic-sector details into a right-side assumptions sheet.
- Surface warnings inline only when a setting materially affects credibility.

### Review Evidence In Place

- Keep the financial chart visible while the strategy is configured.
- Preview indicators and signal markers before running a full research job.
- Replace the long evidence page with tabs for Overview, Equity & Drawdown, Trades, Robustness, and Assumptions.
- Keep verdicts subordinate to the actual return, drawdown, exposure, and holdout evidence.

## shadcn/ui Mapping

shadcn/ui supplies open, editable component source rather than a closed runtime widget library. It requires a React application and Tailwind-based styling, so it should arrive with the planned React/TypeScript migration rather than being mixed into the current vanilla DOM implementation.

| Product interaction | shadcn/ui building blocks |
| --- | --- |
| Template and catalogue search | `Command`, `CommandDialog`, `Badge` |
| Research context bar | `ButtonGroup`, `Select`, `Popover` |
| Editable rule sentence | `Badge`, `Popover`, `Slider`, `Input`, `ToggleGroup` |
| Advanced test assumptions | `Sheet`, `Accordion`, `Field`, `Tooltip` |
| Builder and chart workspace | `ResizablePanelGroup`, `Card`, `Separator` |
| Evidence navigation | `Tabs`, `ScrollArea`, `Progress` |
| Trade ledger | `Table` or TanStack-powered `DataTable` |
| Jobs and feedback | `Sonner`, `Spinner`, `Skeleton`, `Alert` |

Use TradingView Lightweight Charts for candlesticks, volume, linked panes, crosshairs, markers, and financial-series interactions. shadcn charts are suitable for summary analytics, but they are not a replacement for a purpose-built financial chart.

## Recommended Frontend Architecture

- Use Vite, React, and TypeScript under `app/`; build static assets for FastAPI to serve.
- Keep FastAPI, DuckDB, and all current HTTP contracts unchanged during the UI migration.
- Add a typed API client generated from or checked against the FastAPI OpenAPI schema.
- Keep research workflow state in one explicit store so template, catalogue, proposal, and run selections cannot overlap.
- Preserve the existing dark terminal palette through CSS variables, then map those variables to shadcn theme tokens.
- Do not add Next.js or a Node server; this local-first product does not require server-side rendering.

## Delivery Sequence

1. **Complete:** define design tokens, frontend types, and API contracts in a dedicated migration branch.
2. **Complete:** build the React shell, command palette, context bar, and responsive resizable workspace.
3. **Complete:** port Strategy Lab as the first vertical slice, including component and browser contract tests.
4. **Complete:** add Lightweight Charts with candles, volume, indicators, markers, and linked hover details.
5. **Next:** complete manual browser and accessibility review, then port Stock Observatory and Market Pulse. Option Lab is handled by the 0.5 lifecycle canvas.
6. **Later:** remove the vanilla implementation only after every primary workflow passes browser tests.

## Acceptance Criteria

- A user can start from natural language, a template, or a saved strategy without conflicting UI state.
- The common path requires no more than strategy selection, ticker selection, and one Run action.
- Parameter editing occurs in context and updates a visible rule sentence and chart preview.
- Advanced assumptions are discoverable but do not occupy the main canvas.
- Keyboard users can select strategies, edit rules, run research, and inspect evidence.
- Existing API payloads and historical results remain unchanged throughout the frontend migration.

## References

- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite)
- [shadcn/ui component catalogue](https://ui.shadcn.com/docs/components)
- [shadcn/ui Command](https://ui.shadcn.com/docs/components/aria/command)
- [shadcn/ui Resizable](https://ui.shadcn.com/docs/components/base/resizable)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Lightweight Charts React integration](https://tradingview.github.io/lightweight-charts/tutorials/react/advanced)
