import { Activity, ArrowRight, Clock3, ListChecks } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { CurrentSignal, SignalRuleValue, Trade } from "@/lib/types"
import { cn } from "@/lib/utils"

function label(key: string) {
  return key.replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/\b\w/g, (character) => character.toUpperCase())
}

function value(value: SignalRuleValue) {
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(2)
  if (typeof value === "boolean") return value ? "Yes" : "No"
  return value ?? "Unavailable"
}

function stateVariant(state: string) {
  if (state === "SHORT") return "destructive" as const
  if (state === "CASH") return "secondary" as const
  return "default" as const
}

function RuleValues({ values }: { values: Record<string, SignalRuleValue> }) {
  const entries = Object.entries(values)
  if (!entries.length) return <p className="text-xs text-muted-foreground">This strategy does not expose numeric indicator values.</p>
  return <div aria-label="Current rule values" className="flex flex-wrap gap-2">{entries.map(([key, item]) => <span key={key} className="rounded-md border bg-background/60 px-2.5 py-1.5 font-mono text-[10px]"><span className="text-muted-foreground">{label(key)}</span> <strong>{value(item)}</strong></span>)}</div>
}

export function CurrentSignalPanel({ signal, trades }: { signal?: CurrentSignal; trades: Trade[] }) {
  if (!signal) return <Alert><Activity /><AlertTitle>Current Signal Requires A Fresh Run</AlertTitle><AlertDescription>This result predates the Release 0.10 signal contract. Rerun it to derive the current target from the same deterministic engine.</AlertDescription></Alert>
  const transition = signal.latestTransition
  const latestTrade = trades.at(-1)
  return <div className="grid gap-4 xl:grid-cols-2">
    <Card className="gap-4 border-primary/25 bg-primary/5"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.12em] text-primary"><Activity className="size-4" />Current Signal</div><CardTitle className="flex items-center gap-2 text-2xl"><Badge variant={stateVariant(signal.targetState)} className="px-3 py-1 text-base">{signal.targetState}</Badge><span className="text-sm font-normal text-muted-foreground">Target State</span></CardTitle><CardDescription className="mt-2">Observed after the {signal.observationDate} session close.</CardDescription></div><Badge variant={signal.pendingAtNextOpen ? "default" : "outline"}>{signal.pendingAtNextOpen ? "Pending Next Open" : `Executed ${signal.executedState}`}</Badge></div></CardHeader><CardContent className="space-y-4"><p className="text-sm leading-6">{signal.reason}</p><RuleValues values={signal.ruleValues} /><div className="rounded-md border bg-background/55 p-3 text-xs leading-5 text-muted-foreground"><Clock3 className="mr-1 inline size-3" />{signal.executionTiming}</div><p className="text-[10px] text-muted-foreground">The target is deterministic research output, not a trade recommendation.</p></CardContent></Card>
    <Card className="gap-0"><CardHeader className="border-b"><div className="flex items-center gap-2"><ArrowRight className="size-4 text-primary" /><CardTitle>Latest Transition</CardTitle></div><CardDescription>The most recent rule change is visible without opening the full ledger.</CardDescription></CardHeader><CardContent className="space-y-4 pt-5">{transition ? <div className="space-y-3"><div className="flex flex-wrap items-center gap-2"><Badge variant={stateVariant(transition.fromState)}>{transition.fromState}</Badge><ArrowRight className="size-4 text-muted-foreground" /><Badge variant={stateVariant(transition.toState)}>{transition.toState}</Badge><span className="ml-auto font-mono text-[10px] text-muted-foreground">Signal {transition.signalDate} · {transition.executionDate ? `Executed ${transition.executionDate}` : "Next open pending"}</span></div><p className="text-sm leading-6">{transition.reason}</p>{transition.executionPrice !== null && <p className="text-xs text-muted-foreground">Next-open fill: <strong className="text-foreground">${transition.executionPrice.toFixed(2)}</strong></p>}<RuleValues values={transition.ruleValues} /></div> : <p className="text-sm text-muted-foreground">No position transition occurred in this evaluation window.</p>}<div className="border-t pt-4"><div className="mb-3 flex items-center gap-2"><ListChecks className="size-4 text-primary" /><strong className="text-sm">Latest Trade</strong></div>{latestTrade ? <div className="grid gap-2 text-xs sm:grid-cols-2"><span>Entry <strong>{latestTrade.entryDate} @ ${latestTrade.entryPrice.toFixed(2)}</strong></span><span>Status <strong>{latestTrade.status}</strong></span><span>{latestTrade.exitDate ? "Exit" : "Marked"} <strong>{latestTrade.exitDate || latestTrade.asOfDate || "—"} @ ${latestTrade.exitPrice.toFixed(2)}</strong></span><span>P&amp;L <strong className={cn(latestTrade.pnl >= 0 ? "text-primary" : "text-destructive")}>{latestTrade.pnl.toFixed(2)} ({latestTrade.pnlPercent.toFixed(2)}%)</strong></span></div> : <p className="text-xs text-muted-foreground">No trade has executed in this evaluation window.</p>}</div></CardContent></Card>
  </div>
}
