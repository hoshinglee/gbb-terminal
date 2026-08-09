import { Database, Play, Settings2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { PaperPositionHistorySheet } from "@/features/option-lab/paper-position-history-sheet"
import { SimulationHistorySheet } from "@/features/option-lab/simulation-history-sheet"
import type { OptionPositionCreate, OptionPositionState, OptionSimulationRunSummary } from "@/lib/types"

function numericValue(value: string, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function AssumptionsSheet({ draft, onChange }: { draft: OptionPositionCreate; onChange: (draft: OptionPositionCreate) => void }) {
  return <Sheet><SheetTrigger asChild><Button variant="outline"><Settings2 />Model Assumptions</Button></SheetTrigger><SheetContent className="sm:max-w-md"><SheetHeader className="border-b"><SheetTitle>Model Assumptions</SheetTitle><SheetDescription>These inputs affect theoretical valuation and paths. They are not pulled silently from a broker or forecast service.</SheetDescription></SheetHeader><div className="space-y-5 px-4">
    <label className="block space-y-2 text-sm"><span>Interest Rate</span><div className="relative"><Input aria-label="Annual interest rate" type="number" min="-5" max="50" step="0.1" value={Number((draft.interest_rate * 100).toFixed(2))} onChange={(event) => onChange({ ...draft, interest_rate: numericValue(event.target.value) / 100 })} /><span className="pointer-events-none absolute right-3 top-2 text-xs text-muted-foreground">%</span></div><small className="text-muted-foreground">Annualized continuously compounded model input.</small></label>
    <label className="block space-y-2 text-sm"><span>Dividend Yield</span><div className="relative"><Input aria-label="Annual dividend yield" type="number" min="0" max="50" step="0.1" value={Number((draft.dividend_yield * 100).toFixed(2))} onChange={(event) => onChange({ ...draft, dividend_yield: numericValue(event.target.value) / 100 })} /><span className="pointer-events-none absolute right-3 top-2 text-xs text-muted-foreground">%</span></div><small className="text-muted-foreground">Affects early-exercise economics and theoretical value.</small></label>
    <label className="block space-y-2 text-sm"><span>Modeled Paths</span><Input aria-label="Monte Carlo path count" type="number" min="50" max="2000" step="50" value={draft.paths} onChange={(event) => onChange({ ...draft, paths: numericValue(event.target.value, 200) })} /><small className="text-muted-foreground">The UI displays a representative subset; the API evaluates the requested count.</small></label>
    <label className="block space-y-2 text-sm"><span>Random Seed</span><Input aria-label="Monte Carlo random seed" type="number" step="1" value={draft.seed} onChange={(event) => onChange({ ...draft, seed: numericValue(event.target.value, 42) })} /><small className="text-muted-foreground">Keep the seed fixed to reproduce the same modeled paths.</small></label>
  </div><div className="mt-auto border-t p-4 text-xs leading-5 text-muted-foreground">American equity options are modeled with a Cox-Ross-Rubinstein tree. Taxes, bid-ask depth, pin risk, and broker-specific margin are not modeled.</div></SheetContent></Sheet>
}

export function OptionContextBar({ draft, chainReady, chainLoading, running, runs, runsLoading, positions, positionsLoading, onChange, onLoadChain, onSimulate, onRefreshRuns, onLoadRun, onRefreshPositions, onLoadPosition }: {
  draft: OptionPositionCreate
  chainReady: boolean
  chainLoading: boolean
  running: boolean
  runs: OptionSimulationRunSummary[]
  runsLoading: boolean
  positions: OptionPositionState[]
  positionsLoading: boolean
  onChange: (draft: OptionPositionCreate) => void
  onLoadChain: () => void
  onSimulate: () => void
  onRefreshRuns: () => void
  onLoadRun: (runId: string) => Promise<void>
  onRefreshPositions: () => void
  onLoadPosition: (positionId: string) => Promise<void>
}) {
  const expiration = draft.legs[0]?.expiration || "No Expiry"
  return <div role="region" aria-label="Option simulation controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6">
    <Input aria-label="Option ticker" className="w-24 font-mono font-semibold uppercase" value={draft.ticker} maxLength={12} onChange={(event) => { const ticker = event.target.value.toUpperCase(); const generatedName = draft.name.startsWith(`${draft.ticker} `) ? `${ticker}${draft.name.slice(draft.ticker.length)}` : draft.name; onChange({ ...draft, ticker, name: generatedName }) }} />
    <div className="relative"><Input aria-label="Underlying spot price" className="w-32 pl-7 font-mono" type="number" min="0.01" step="0.01" value={draft.underlying_price} onChange={(event) => { const underlyingPrice = numericValue(event.target.value); onChange({ ...draft, underlying_price: underlyingPrice, share_cost_basis: ["covered_call", "conversion"].includes(draft.position_kind) ? underlyingPrice : draft.share_cost_basis }) }} /><span className="pointer-events-none absolute left-3 top-2 text-xs text-muted-foreground">$</span></div>
    <div className="hidden items-center gap-2 lg:flex"><Badge variant="secondary">{draft.position_kind.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</Badge><Badge variant="outline">{expiration}</Badge><Badge variant="outline">{draft.legs.length} {draft.legs.length === 1 ? "Leg" : "Legs"}</Badge></div>
    <div className="ml-0 flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto"><Button variant="outline" className="flex-1 sm:flex-none" onClick={onLoadChain} disabled={chainLoading}><Database className={chainLoading ? "motion-safe:animate-pulse" : ""} />{chainLoading ? "Loading…" : chainReady ? "Refresh Chain" : "Load Chain"}</Button><SimulationHistorySheet runs={runs} loading={runsLoading} onRefresh={onRefreshRuns} onLoad={onLoadRun} /><PaperPositionHistorySheet positions={positions} loading={positionsLoading} onRefresh={onRefreshPositions} onLoad={onLoadPosition} /><AssumptionsSheet draft={draft} onChange={onChange} /><Button className="flex-1 sm:flex-none" onClick={onSimulate} disabled={running}><Play className={running ? "motion-safe:animate-pulse" : ""} /><span aria-live="polite">{running ? "Simulating…" : "Simulate Position"}</span></Button></div>
    <div className="w-full text-[10px] text-muted-foreground lg:hidden">{draft.position_kind.replaceAll("_", " ")} · {expiration} · {draft.legs.length} {draft.legs.length === 1 ? "leg" : "legs"}</div>
  </div>
}
