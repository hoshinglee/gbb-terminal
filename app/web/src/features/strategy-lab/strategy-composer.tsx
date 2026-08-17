import { ArrowRight, BookOpen, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import type { StrategyTemplate } from "@/lib/types"
import { ParameterChip } from "@/features/strategy-lab/parameter-chip"
import { TrailingStopChip } from "@/features/strategy-lab/trailing-stop-chip"
import { useResearchWorkspace } from "@/features/strategy-lab/workspace"

const prompts = [
  "Long when SMA 10 crosses above SMA 50 and exit on the reverse crossover.",
  "Buy when RSI 14 falls below 30; exit above 55 with a 6% trailing stop.",
  "Enter a 20-bar Darvas breakout after 3 confirmations when volume is 1.5 times its 20-day average.",
]

export const starterStrategies = [
  { templateId: "sma-crossover", title: "Trend Following", thesis: "Stay invested while a faster trend remains above a slower trend." },
  { templateId: "rsi-mean-reversion", title: "Buy The Dip", thesis: "Enter after an oversold reading and leave after recovery." },
  { templateId: "donchian-breakout", title: "Breakout", thesis: "Enter new channel highs and leave on shorter-term weakness." },
  { templateId: "benchmark-relative-strength", title: "Relative Strength", thesis: "Own one stock only while it outperforms a visible reference." },
  { templateId: "macd-trend", title: "Momentum", thesis: "Follow a MACD trend and optionally add a visible trailing stop." },
  { templateId: "relative-strength-rotation", title: "Ranked Leaders", thesis: "Rank a small explicit universe and hold its strongest members." },
]

const ruleClassName = "flex flex-wrap items-center gap-1.5 text-sm leading-8 sm:text-base"

function RuleSentence({ template }: { template: StrategyTemplate }) {
  const { state } = useResearchWorkspace()
  if (state.selection.kind !== "template") return null
  const parameters = Object.fromEntries(template.parameters.map((parameter) => [parameter.key, <ParameterChip key={parameter.key} parameter={parameter} />]))
  const kind = template.rule_graph.kind
  if (kind === "crossover") return <p className={ruleClassName}>Long when {parameters.fast_window} crosses above {parameters.slow_window}; exit on the reverse crossover.</p>
  if (kind === "macd") return <p className={ruleClassName}>Long when MACD {parameters.fast_window} / {parameters.slow_window} crosses its {parameters.signal_window} signal; exit on reversal.</p>
  if (kind === "threshold") return <p className={ruleClassName}>Long when RSI {parameters.window} falls below {parameters.entry_level}; exit after recovery through {parameters.exit_level}.</p>
  if (kind === "bollinger") return <p className={ruleClassName}>Long below the {parameters.window}-bar lower band at {parameters.deviations} deviations; exit through the middle band.</p>
  if (kind === "donchian") return <p className={ruleClassName}>Long above the prior {parameters.entry_window}-bar high; exit below the {parameters.exit_window}-bar low.</p>
  if (kind === "darvas_volume") return <p className={ruleClassName}>Long a {parameters.box_window}-bar Darvas breakout after {parameters.confirmation_bars} confirmations when volume exceeds {parameters.volume_multiplier} times its {parameters.volume_window}-bar average.</p>
  if (kind === "fibonacci") return <p className={ruleClassName}>Long a breakout through the {parameters.ratio} retracement from a deterministic {parameters.window}-bar swing.</p>
  if (kind === "relative_strength") return <p className={ruleClassName}>For one stock, enter when its {parameters.window}-session return beats the selected reference by {parameters.entry_threshold}; exit when relative performance turns negative.</p>
  if (kind === "ranked_portfolio") return <p className={ruleClassName}>Across an explicit universe, every {parameters.rebalance_sessions} sessions rank stocks by {parameters.lookback_window}-session return and equally hold the top {parameters.top_n}.</p>
  return <p className="text-sm leading-7 sm:text-base">{template.description}</p>
}

export function StrategyComposer({ templates, onOpenCommand }: { templates: StrategyTemplate[]; onOpenCommand: () => void }) {
  const { state, dispatch } = useResearchWorkspace()
  const selection = state.selection
  const quickStarts = starterStrategies.flatMap((starter) => {
    const template = templates.find((item) => item.template_id === starter.templateId)
    return template ? [{ ...starter, template }] : []
  })
  if (selection.kind === "template") return (
    <Card className="h-full overflow-y-auto rounded-none border-0 bg-card/80 shadow-none">
      <CardHeader className="border-b"><div className="flex items-start justify-between gap-3"><div><div className="mb-2 flex gap-2"><Badge>{selection.template.family}</Badge><Badge variant="outline">{selection.origin === "catalogue" ? "Saved Configuration" : "Validated Template"}</Badge></div><CardTitle className="text-xl">{selection.instance.name}</CardTitle><CardDescription>{selection.instance.description}</CardDescription></div><Button variant="outline" size="sm" onClick={onOpenCommand}><BookOpen />Change</Button></div></CardHeader>
      <CardContent className="space-y-5 p-6"><div className="rounded-lg border bg-background/60 p-4"><p className="mb-2 font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Editable Rule</p><RuleSentence template={selection.template} /></div><TrailingStopChip /><div className="flex flex-wrap gap-2 text-xs text-muted-foreground"><span>Click any highlighted value to edit it in context.</span>{Object.values(selection.instance.parameter_modes).includes("search") && <Badge variant="secondary">Guarded parameter search enabled</Badge>}</div><Button variant="ghost" size="sm" onClick={() => dispatch({ type: "edit-instruction", instruction: "" })}><Sparkles />Start instead from natural language</Button></CardContent>
    </Card>
  )
  if (selection.kind === "catalogue") return <Card className="h-full overflow-y-auto rounded-none border-0"><CardHeader><Badge className="w-fit">Saved Legacy Strategy</Badge><CardTitle>{selection.strategy.name}</CardTitle><CardDescription>{selection.strategy.description}</CardDescription></CardHeader><CardContent><p className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">This earlier strategy has no editable V2 parameter model. It can still run unchanged, or you can replace it from the command palette.</p><Button className="mt-4" variant="outline" onClick={onOpenCommand}>Choose Another Strategy</Button></CardContent></Card>
  const instruction = selection.kind === "instruction" ? selection.instruction : ""
  return (
    <Card className="h-full overflow-y-auto rounded-none border-0 bg-card/80 shadow-none">
      <CardHeader><Badge variant="outline" className="w-fit border-primary/30 text-primary"><Sparkles />Strategy Composer</Badge><CardTitle className="text-2xl">Express the idea first.</CardTitle><CardDescription>Describe the signal in plain language, or start from a validated research pattern.</CardDescription></CardHeader>
      <CardContent className="space-y-5"><Textarea autoFocus value={instruction === "Describe your strategy here…" ? "" : instruction} onChange={(event) => dispatch({ type: "edit-instruction", instruction: event.target.value })} placeholder="Long when the 10-day SMA crosses above the 50-day SMA; exit on the reverse crossover…" className="min-h-36 resize-none border-primary/20 bg-background/70 text-base leading-7" /><div className="flex flex-wrap gap-2">{prompts.map((prompt) => <button key={prompt} type="button" onClick={() => dispatch({ type: "edit-instruction", instruction: prompt })} className="rounded-full border bg-muted/30 px-3 py-1.5 text-left text-xs text-muted-foreground transition hover:border-primary/40 hover:text-foreground">{prompt}</button>)}</div><div className="flex items-center gap-3"><div className="h-px flex-1 bg-border" /><span className="font-mono text-[9px] text-muted-foreground">OR START WITH A RESEARCH THESIS</span><div className="h-px flex-1 bg-border" /></div><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{quickStarts.map(({ template, title, thesis }) => <button key={template.template_id} type="button" onClick={() => dispatch({ type: "select-template", template })} className="group rounded-lg border bg-background/50 p-3 text-left transition hover:border-primary/40 hover:bg-primary/5"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{title}</span><ArrowRight className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" /></div><p className="mt-2 text-xs leading-5 text-muted-foreground">{thesis}</p><Badge variant="outline" className="mt-3 text-[9px]">{template.rule_graph.kind === "ranked_portfolio" ? "Small Portfolio" : template.name}</Badge></button>)}</div><Button variant="outline" onClick={onOpenCommand}><BookOpen />Browse All Templates And Saved Strategies</Button></CardContent>
    </Card>
  )
}
