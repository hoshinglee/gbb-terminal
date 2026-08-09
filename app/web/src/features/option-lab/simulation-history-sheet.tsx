import { useState } from "react"
import { History, RotateCcw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import type { OptionSimulationRunSummary } from "@/lib/types"

function displayKind(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function SimulationHistorySheet({ runs, loading, onRefresh, onLoad }: {
  runs: OptionSimulationRunSummary[]
  loading: boolean
  onRefresh: () => void
  onLoad: (runId: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [loadingRunId, setLoadingRunId] = useState("")
  const load = async (runId: string) => {
    setLoadingRunId(runId)
    await onLoad(runId)
    setLoadingRunId("")
    setOpen(false)
  }
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline"><History />Runs{runs.length ? <Badge variant="secondary">{runs.length}</Badge> : null}</Button></SheetTrigger><SheetContent className="sm:max-w-lg"><SheetHeader className="border-b"><SheetTitle>Option Research Runs</SheetTitle><SheetDescription>Every simulation is immutable and local. Loading a run restores its exact position request, model assumptions, seed, and evidence.</SheetDescription></SheetHeader><div className="flex items-center justify-between gap-2 px-4"><span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground">Newest First</span><Button size="sm" variant="ghost" onClick={onRefresh} disabled={loading}><RotateCcw className={loading ? "motion-safe:animate-spin" : ""} />Refresh</Button></div><ScrollArea className="min-h-0 flex-1 px-4"><div className="space-y-2 pb-6">{runs.length ? runs.map((run) => <button type="button" key={run.runId} className="w-full rounded-lg border p-3 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => void load(run.runId)} disabled={Boolean(loadingRunId)}><div className="flex items-start justify-between gap-3"><div><strong className="text-sm">{run.runName || `${run.ticker} ${displayKind(run.positionKind)}`}</strong><p className="mt-1 text-[10px] text-muted-foreground">{run.ticker} · {displayKind(run.positionKind)} · {run.request.legs.length} {run.request.legs.length === 1 ? "leg" : "legs"}</p></div><Badge variant="outline">{loadingRunId === run.runId ? "Loading" : new Date(run.createdAt).toLocaleDateString()}</Badge></div><div className="mt-3 flex flex-wrap gap-2 font-mono text-[9px] text-muted-foreground"><span>{run.modelVersion}</span><span>•</span><span>{run.request.paths} paths</span><span>•</span><span>{run.summary.breakEvens?.length ? `BE ${run.summary.breakEvens.join(" / ")}` : "No BE in range"}</span></div></button>) : <div className="grid h-64 place-items-center rounded-lg border border-dashed text-center text-sm text-muted-foreground">No persisted option simulations yet.</div>}</div></ScrollArea></SheetContent></Sheet>
}
