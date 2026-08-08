import { Search, SlidersHorizontal } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Slider } from "@/components/ui/slider"
import type { ParameterSpec, ParameterValue } from "@/lib/types"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

export function ParameterChip({ parameter }: { parameter: ParameterSpec }) {
  const { state, dispatch } = useResearchWorkspace()
  if (state.selection.kind !== "template") return null
  const value = state.selection.instance.parameter_values[parameter.key]
  const mode = state.selection.instance.parameter_modes[parameter.key] || "fixed"
  const numeric = parameter.parameter_type === "integer" || parameter.parameter_type === "number"
  const numberValue = Number(value)
  const minimum = parameter.minimum ?? numberValue
  const maximum = parameter.maximum ?? numberValue
  const range = state.ranges[parameter.key] || { minimum, maximum }
  const updateValue = (next: ParameterValue) => dispatch({ type: "update-parameter", key: parameter.key, value: next })
  return (
    <Popover>
      <PopoverTrigger asChild><button type="button" className="inline-flex items-center gap-1.5 rounded-md border border-primary/35 bg-primary/10 px-2 py-0.5 font-mono text-xs text-primary transition hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"><SlidersHorizontal className="size-3" />{parameter.label} {String(value)}{parameter.unit === "Sessions" ? "" : parameter.unit}<span className="sr-only">Edit {parameter.label}</span></button></PopoverTrigger>
      <PopoverContent className="w-80 space-y-4" align="start">
        <div><div className="flex items-center justify-between"><span className="font-medium">{parameter.label}</span><Badge variant="outline" className="font-mono text-[9px]">{parameter.unit || "Value"}</Badge></div><p className="mt-1 text-xs text-muted-foreground">Edit this rule where it appears. No separate configuration form is required.</p></div>
        {numeric && <><Slider value={[numberValue]} min={minimum} max={maximum} step={parameter.step || 1} onValueChange={([next]) => updateValue(parameter.parameter_type === "integer" ? Math.round(next) : next)} /><Input type="number" value={numberValue} min={minimum} max={maximum} step={parameter.step || 1} onChange={(event) => updateValue(parameter.parameter_type === "integer" ? Number.parseInt(event.target.value, 10) : Number(event.target.value))} /></>}
        {parameter.parameter_type === "boolean" && <Button variant={value ? "default" : "outline"} onClick={() => updateValue(!value)}>{value ? "Enabled" : "Disabled"}</Button>}
        <div className="flex gap-2 border-t pt-3"><Button size="sm" variant={mode === "fixed" ? "default" : "outline"} onClick={() => dispatch({ type: "update-parameter-mode", key: parameter.key, mode: "fixed" })}>Fixed</Button>{parameter.searchable && <Button size="sm" variant={mode === "search" ? "default" : "outline"} onClick={() => dispatch({ type: "update-parameter-mode", key: parameter.key, mode: "search" })}><Search />Explore Range</Button>}</div>
        {mode === "search" && <div className="grid grid-cols-2 gap-3"><label className="space-y-1 text-xs text-muted-foreground">Minimum<Input type="number" value={range.minimum} step={parameter.step || 1} onChange={(event) => dispatch({ type: "update-range", key: parameter.key, range: { ...range, minimum: Number(event.target.value) } })} /></label><label className="space-y-1 text-xs text-muted-foreground">Maximum<Input type="number" value={range.maximum} step={parameter.step || 1} onChange={(event) => dispatch({ type: "update-range", key: parameter.key, range: { ...range, maximum: Number(event.target.value) } })} /></label></div>}
      </PopoverContent>
    </Popover>
  )
}
