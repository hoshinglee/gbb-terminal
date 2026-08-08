import { ShieldCheck, SlidersHorizontal, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Slider } from "@/components/ui/slider"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

const DEFAULT_TRAILING_STOP = 8

export function TrailingStopChip() {
  const { state, dispatch } = useResearchWorkspace()
  if (state.selection.kind !== "template") return null
  const current = state.selection.instance.risk.trailing_stop_percent
  const update = (value: number) => {
    if (!Number.isFinite(value)) return
    dispatch({ type: "update-risk", key: "trailing_stop_percent", value: Math.min(50, Math.max(1, value)) })
  }
  if (current === undefined) {
    return <Button type="button" size="sm" variant="outline" onClick={() => update(DEFAULT_TRAILING_STOP)}><ShieldCheck />Add Trailing Stop</Button>
  }
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs leading-6 text-muted-foreground">
      <ShieldCheck className="size-4 text-primary" />
      <span>Protect gains when the close retreats</span>
      <Popover>
        <PopoverTrigger asChild><button type="button" className="inline-flex items-center gap-1.5 rounded-md border border-primary/35 bg-primary/10 px-2 py-0.5 font-mono text-xs text-primary transition hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><SlidersHorizontal className="size-3" />Trailing Stop {current}%</button></PopoverTrigger>
        <PopoverContent className="w-80 space-y-4" align="start">
          <div><p className="font-medium">Trailing Stop</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Measured from the most favorable close after the next-open entry. A close breach signals an exit for the following session open.</p></div>
          <Slider value={[current]} min={1} max={50} step={0.5} onValueChange={([value]) => update(value)} />
          <label className="space-y-2 text-xs text-muted-foreground">Distance (%)<Input type="number" value={current} min={1} max={50} step={0.5} onChange={(event) => update(Number(event.target.value))} /></label>
        </PopoverContent>
      </Popover>
      <span>from its most favorable close.</span>
      <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove trailing stop" onClick={() => dispatch({ type: "update-risk", key: "trailing_stop_percent", value: null })}><X /></Button>
    </div>
  )
}
