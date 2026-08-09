import { Command, Play, Settings2 } from "lucide-react"

import { AssumptionsSheet } from "@/features/strategy-lab/assumptions-sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Timeframe } from "@/lib/types"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

export function ResearchContextBar({ running, onRun, onOpenCommand }: { running: boolean; onRun: () => void; onOpenCommand: () => void }) {
  const { state, dispatch } = useResearchWorkspace()
  const portfolio = state.selection.kind === "template" && state.selection.template.rule_graph.kind === "ranked_portfolio"
  const strategyName = state.selection.kind === "template" ? state.selection.instance.name : state.selection.kind === "catalogue" ? state.selection.strategy.name : state.selection.kind === "instruction" ? "Natural Language Strategy" : "No Strategy Selected"
  return (
    <div role="region" aria-label="Research controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6">
      <Button aria-label={`Choose strategy. Current selection: ${strategyName}`} variant="outline" className="w-full justify-between sm:w-auto sm:min-w-52" onClick={onOpenCommand}><span className="truncate">{strategyName}</span><span className="flex items-center gap-1 font-mono text-[9px] text-muted-foreground"><Command aria-hidden="true" className="size-3" />K</span></Button>
      {!portfolio && <Input aria-label="Research ticker" className="w-24 font-mono font-semibold uppercase" value={state.ticker} maxLength={12} onChange={(event) => dispatch({ type: "update-context", field: "ticker", value: event.target.value.toUpperCase() })} />}
      <Select value={state.timeframe} onValueChange={(value: Timeframe) => dispatch({ type: "update-timeframe", value })}><SelectTrigger aria-label="Backtest window" className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="1mo">1 Month</SelectItem><SelectItem value="3mo">3 Months</SelectItem><SelectItem value="6mo">6 Months</SelectItem><SelectItem value="1y">1 Year</SelectItem><SelectItem value="2y">2 Years</SelectItem></SelectContent></Select>
      <div className="hidden items-center gap-2 lg:flex"><Badge variant="secondary">{state.benchmark}</Badge><Badge variant="outline">{state.commissionBps + state.slippageBps} bps</Badge><Badge variant="outline">Next Open</Badge></div>
      <div className="ml-0 flex w-full items-center gap-2 sm:ml-auto sm:w-auto"><AssumptionsSheet /><Button className="flex-1 sm:flex-none" onClick={onRun} disabled={running || state.selection.kind === "none"}><Play aria-hidden="true" className={running ? "motion-safe:animate-pulse" : ""} /><span aria-live="polite">{running ? "Running Research…" : "Run Research"}</span></Button></div>
      <div className="w-full text-[10px] text-muted-foreground lg:hidden"><Settings2 className="mr-1 inline size-3" />{state.benchmark} · {state.commissionBps + state.slippageBps} bps · Next Open</div>
    </div>
  )
}
