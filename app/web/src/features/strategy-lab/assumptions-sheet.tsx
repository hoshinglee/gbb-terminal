import { ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

export function AssumptionsSheet() {
  const { state, dispatch } = useResearchWorkspace()
  const relativeStrength = state.selection.kind === "template" && state.selection.template.template_id === "benchmark-relative-strength"
  const portfolio = state.selection.kind === "template" && state.selection.template.rule_graph.kind === "ranked_portfolio"
  return (
    <Sheet>
      <SheetTrigger asChild><Button variant="outline" size="sm"><ShieldCheck />Assumptions</Button></SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>Research Assumptions</SheetTitle><SheetDescription>Advanced settings remain available without dominating the research canvas.</SheetDescription></SheetHeader>
        <div className="space-y-6 px-4 pb-8">
          <section className="space-y-4"><div className="flex items-center justify-between"><h3 className="font-medium">Execution</h3><Badge variant="secondary">Next Session Open</Badge></div><div className="grid grid-cols-2 gap-3"><label className="space-y-2 text-xs text-muted-foreground">Commission (bps)<Input type="number" min={0} max={100} step={0.5} value={state.commissionBps} onChange={(event) => dispatch({ type: "update-cost", field: "commissionBps", value: Number(event.target.value) })} /></label><label className="space-y-2 text-xs text-muted-foreground">Slippage (bps)<Input type="number" min={0} max={100} step={0.5} value={state.slippageBps} onChange={(event) => dispatch({ type: "update-cost", field: "slippageBps", value: Number(event.target.value) })} /></label></div><p className="text-xs leading-5 text-muted-foreground">Zero costs are the default educational assumption. Cost sensitivity remains visible in evidence.</p></section>
          <Separator />
          <section className="space-y-4"><h3 className="font-medium">Comparison</h3><label className="space-y-2 text-xs text-muted-foreground">Market Benchmark<Input value={state.benchmark} maxLength={12} onChange={(event) => dispatch({ type: "update-context", field: "benchmark", value: event.target.value.toUpperCase() })} /></label>{relativeStrength && <><label className="space-y-2 text-xs text-muted-foreground">Stock Return Compared With<Select value={state.relativeStrengthReference} onValueChange={(value: "market" | "sector" | "custom") => dispatch({ type: "update-relative-reference", value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="market">Selected Market Benchmark</SelectItem><SelectItem value="sector">Detected Sector ETF</SelectItem><SelectItem value="custom">Explicit Comparison Symbol</SelectItem></SelectContent></Select><span>The detected sector ETF is shown in evidence and can be overridden; no peer is silently inferred.</span></label>{state.relativeStrengthReference === "custom" && <label className="space-y-2 text-xs text-muted-foreground">Comparison Symbol<Input value={state.relativeStrengthSymbol} placeholder="QQQ" onChange={(event) => dispatch({ type: "update-context", field: "relativeStrengthSymbol", value: event.target.value.toUpperCase() })} /></label>}</>}{portfolio && <label className="space-y-2 text-xs text-muted-foreground">Stocks To Rank<Input value={state.universe} onChange={(event) => dispatch({ type: "update-context", field: "universe", value: event.target.value })} /><span>Enter comma-separated US symbols. This portfolio strategy ranks only these stocks and never invents peers.</span></label>}</section>
          <Separator />
          <section className="space-y-5"><h3 className="font-medium">Validation Design</h3><label className="block space-y-3 text-xs text-muted-foreground"><span className="flex justify-between"><span>Training Fraction</span><span>{Math.round(state.validation.training_fraction * 100)}%</span></span><Slider value={[state.validation.training_fraction]} min={0.5} max={0.8} step={0.05} onValueChange={([value]) => dispatch({ type: "update-validation", field: "training_fraction", value })} /></label><label className="block space-y-3 text-xs text-muted-foreground"><span className="flex justify-between"><span>Untouched Final Test</span><span>{Math.round(state.validation.final_test_fraction * 100)}%</span></span><Slider value={[state.validation.final_test_fraction]} min={0.1} max={0.35} step={0.05} onValueChange={([value]) => dispatch({ type: "update-validation", field: "final_test_fraction", value })} /></label><label className="space-y-2 text-xs text-muted-foreground">Walk-Forward Folds<Input type="number" min={2} max={10} value={state.validation.walk_forward_folds} onChange={(event) => dispatch({ type: "update-validation", field: "walk_forward_folds", value: Number(event.target.value) })} /></label></section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
