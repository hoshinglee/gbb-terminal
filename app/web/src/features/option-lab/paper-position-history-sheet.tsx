import { useState } from "react"
import { BookOpenCheck, RotateCcw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import type { OptionPositionState } from "@/lib/types"

function displayKind(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function PaperPositionHistorySheet({ positions, loading, onRefresh, onLoad }: {
  positions: OptionPositionState[]
  loading: boolean
  onRefresh: () => void
  onLoad: (positionId: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [loadingPositionId, setLoadingPositionId] = useState("")
  const load = async (positionId: string) => {
    setLoadingPositionId(positionId)
    await onLoad(positionId)
    setLoadingPositionId("")
    setOpen(false)
  }
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline"><BookOpenCheck />Positions{positions.length ? <Badge variant="secondary">{positions.length}</Badge> : null}</Button></SheetTrigger><SheetContent className="sm:max-w-lg"><SheetHeader className="border-b"><SheetTitle>Paper Positions</SheetTitle><SheetDescription>Reopen any local ledger and continue from its latest immutable state. These records are simulations, not brokerage positions.</SheetDescription></SheetHeader><div className="flex items-center justify-between gap-2 px-4"><span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground">Recently Updated</span><Button size="sm" variant="ghost" onClick={onRefresh} disabled={loading}><RotateCcw className={loading ? "motion-safe:animate-spin" : ""} />Refresh</Button></div><ScrollArea className="min-h-0 flex-1 px-4"><div className="space-y-2 pb-6">{positions.length ? positions.map((position) => <button type="button" key={position.position_id} className="w-full rounded-lg border p-3 text-left transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onClick={() => void load(position.position_id)} disabled={Boolean(loadingPositionId)}><div className="flex items-start justify-between gap-3"><div><strong className="text-sm">{position.name}</strong><p className="mt-1 text-[10px] text-muted-foreground">{position.ticker} · {position.current_structure || displayKind(position.position_kind)}</p></div><Badge variant={position.status === "open" ? "default" : "outline"}>{loadingPositionId === position.position_id ? "Loading" : position.status.toUpperCase()}</Badge></div><div className="mt-3 flex flex-wrap gap-2 font-mono text-[9px] text-muted-foreground"><span>{position.legs.length} {position.legs.length === 1 ? "leg" : "legs"}</span><span>•</span><span>{position.shares} shares</span><span>•</span><span>{new Date(position.updated_at).toLocaleString()}</span>{position.research_run_id ? <><span>•</span><span>Run {position.research_run_id.slice(0, 8)}</span></> : null}</div></button>) : <div className="grid h-64 place-items-center rounded-lg border border-dashed text-center text-sm text-muted-foreground">No paper positions have been saved yet.</div>}</div></ScrollArea></SheetContent></Sheet>
}
