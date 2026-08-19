import { useEffect, useMemo, useState } from "react"
import { ArrowRight, BarChart3, CalendarDays, Check, Database, LoaderCircle, ShieldCheck, SlidersHorizontal, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { planOptionPositions, runOptionScenario } from "@/lib/api"
import type { OptionOutlook, OptionPlanCandidate, OptionPlanResult, OptionScenarioResult } from "@/lib/types"
import { cn } from "@/lib/utils"
import { futureDate } from "./option-presets"

function money(value: number) {
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
}

function riskValue(value: number | "Unlimited") {
  return typeof value === "number" ? money(Math.abs(value)) : value
}

function numeric(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function plannerError(error: unknown) {
  return error instanceof Error ? error.message : "The options plan could not be prepared."
}

const outlooks: Array<{ value: OptionOutlook; label: string; note: string }> = [
  { value: "bullish", label: "Bullish", note: "I expect a meaningful rise." },
  { value: "bearish", label: "Bearish", note: "I expect weakness or want downside exposure." },
  { value: "neutral", label: "Neutral", note: "I expect a range or want conditional income." },
]

function CandidateCard({ candidate, selected, onSelect, onUse }: { candidate: OptionPlanCandidate; selected: boolean; onSelect: () => void; onUse: () => void }) {
  const debitOrCredit = candidate.netDebit > 0 ? `${money(candidate.netDebit)} Debit` : `${money(candidate.netCredit)} Credit`
  return <Card className={cn("min-w-0 gap-3 py-4 transition-colors", selected && "border-primary/60 bg-primary/[0.04]")}>
    <CardHeader className="px-4 sm:px-5"><button type="button" className="rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" aria-pressed={selected} onClick={onSelect}><span className="flex items-start justify-between gap-3"><span><CardTitle className="text-base">{candidate.name}</CardTitle><CardDescription className="mt-1.5 leading-5">{candidate.tradeoff}</CardDescription></span>{selected && <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground"><Check className="size-3.5" /></span>}</span></button></CardHeader>
    <CardContent className="space-y-3 px-4 sm:px-5">
      <div className="grid grid-cols-2 gap-2 text-xs"><div className="rounded-md border p-2.5"><span className="text-muted-foreground">Entry</span><strong className="mt-1 block">{debitOrCredit}</strong></div><div className="rounded-md border p-2.5"><span className="text-muted-foreground">Capital</span><strong className="mt-1 block">{money(candidate.capitalRequired)}</strong></div><div className="rounded-md border p-2.5"><span className="text-muted-foreground">Maximum Loss</span><strong className="mt-1 block text-destructive">{riskValue(candidate.maximumLoss)}</strong></div><div className="rounded-md border p-2.5"><span className="text-muted-foreground">Maximum Gain</span><strong className="mt-1 block">{riskValue(candidate.maximumGain)}</strong></div></div>
      <div className="space-y-1.5 font-mono text-[10px] text-muted-foreground"><p>{candidate.expiration} · strikes {candidate.strikes.map((strike) => `$${strike}`).join(" / ")}</p><p>Gross structural collateral {money(candidate.collateral)}</p><p>Δ {candidate.greeks.delta.toFixed(2)} · Γ {candidate.greeks.gamma.toFixed(2)} · Θ {candidate.greeks.theta.toFixed(2)} · Vega {candidate.greeks.vega.toFixed(2)}</p></div>
      <div className="flex flex-wrap gap-2"><Badge variant={candidate.withinBudget ? "default" : "destructive"}>{candidate.withinBudget ? "Within Stated Budget" : "Outside Stated Budget"}</Badge><Badge variant="outline">{candidate.quoteQuality}</Badge><Badge variant="secondary">{candidate.profitCharacter}</Badge></div>
      <details className="rounded-md border px-3 py-2 text-xs"><summary className="cursor-pointer font-medium">Inspect Bid / Ask And Break-Even</summary><div className="mt-3 space-y-2 text-muted-foreground">{candidate.quotes.map((quote) => <p key={quote.legId}><strong className="text-foreground">{quote.side.toUpperCase()} {quote.optionType.toUpperCase()} ${quote.strike}</strong> · bid {money(quote.bid)} · ask {money(quote.ask)} · used {quote.premiumSource} {money(quote.premiumUsed)} · IV {quote.impliedVolatility.toFixed(1)}%</p>)}<p>Expiry break-even: {candidate.breakEvens.length ? candidate.breakEvens.map(money).join(", ") : "Not identified"}</p>{candidate.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div></details>
      <Button type="button" variant={selected ? "default" : "outline"} className="w-full" onClick={() => { onSelect(); onUse() }}>Use In Detailed Builder<ArrowRight /></Button>
    </CardContent>
  </Card>
}

export function OptionsPlanner({ ticker, interestRate, dividendYield, onUseCandidate, onProgress }: {
  ticker: string
  interestRate: number
  dividendYield: number
  onUseCandidate: (candidate: OptionPlanCandidate) => void
  onProgress: (stage: 1 | 2 | 3) => void
}) {
  const [outlook, setOutlook] = useState<OptionOutlook>("bullish")
  const [targetDate, setTargetDate] = useState(() => futureDate(45))
  const [targetPrice, setTargetPrice] = useState("")
  const [targetPriceLow, setTargetPriceLow] = useState("")
  const [targetPriceHigh, setTargetPriceHigh] = useState("")
  const [sharesOwned, setSharesOwned] = useState("0")
  const [acquiringShares, setAcquiringShares] = useState(false)
  const [maximumLoss, setMaximumLoss] = useState("")
  const [capitalBudget, setCapitalBudget] = useState("")
  const [plan, setPlan] = useState<OptionPlanResult | null>(null)
  const [selectedId, setSelectedId] = useState("")
  const [planning, setPlanning] = useState(false)
  const [scenarioPrice, setScenarioPrice] = useState("")
  const [scenarioDate, setScenarioDate] = useState(() => futureDate(30))
  const [scenario, setScenario] = useState<OptionScenarioResult | null>(null)
  const [scenarioLoading, setScenarioLoading] = useState(false)

  useEffect(() => {
    setPlan(null)
    setScenario(null)
    setSelectedId("")
    onProgress(1)
  }, [ticker, onProgress])

  const selected = useMemo(() => plan?.candidates.find((candidate) => candidate.candidateId === selectedId) || plan?.candidates[0] || null, [plan, selectedId])

  const buildPlan = async () => {
    if (!ticker.trim()) return toast.error("Enter a US ticker before planning an option position.")
    setPlanning(true)
    try {
      const result = await planOptionPositions({
        ticker,
        outlook,
        target_date: targetDate,
        target_price: numeric(targetPrice),
        target_price_low: numeric(targetPriceLow),
        target_price_high: numeric(targetPriceHigh),
        shares_owned: Math.max(Number(sharesOwned) || 0, 0),
        acquiring_shares_acceptable: acquiringShares,
        maximum_loss: numeric(maximumLoss),
        capital_budget: numeric(capitalBudget),
        interest_rate: interestRate,
        dividend_yield: dividendYield,
      })
      setPlan(result)
      setSelectedId(result.candidates.find((candidate) => candidate.withinBudget)?.candidateId || result.candidates[0]?.candidateId || "")
      setScenarioPrice(String(numeric(targetPrice) || result.underlyingPrice))
      setScenarioDate(targetDate)
      setScenario(null)
      onProgress(2)
      toast.success(`${result.candidates.length} validated structures are ready to compare.`)
    } catch (error) {
      toast.error("Options plan unavailable", { description: plannerError(error) })
    } finally {
      setPlanning(false)
    }
  }

  const modelScenario = async () => {
    if (!selected) return
    const price = numeric(scenarioPrice)
    if (price === null) return toast.error("Enter a scenario price greater than zero.")
    setScenarioLoading(true)
    try {
      const result = await runOptionScenario({ position: selected.position, scenario_price: price, scenario_date: scenarioDate })
      setScenario(result)
      onProgress(3)
    } catch (error) {
      toast.error("Scenario could not be modeled", { description: plannerError(error) })
    } finally {
      setScenarioLoading(false)
    }
  }

  return <section aria-labelledby="options-planner-title" className="space-y-4">
    <Card className="overflow-hidden border-primary/25"><CardHeader className="border-b bg-primary/[0.035]"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.16em] text-primary"><Sparkles className="size-3.5" />1 · Plan</div><CardTitle id="options-planner-title" className="text-xl">Start with your view, not an option chain.</CardTitle><CardDescription className="mt-2 max-w-3xl leading-6">Tell the planner what you think may happen to {ticker || "the stock"}, when, and how much risk you can accept. It compares only structures already validated by the existing Python engine.</CardDescription></div><Badge variant="outline"><Database />Current Public Chain</Badge></div></CardHeader>
      <CardContent className="space-y-5 pt-5">
        <fieldset><legend className="mb-2 text-sm font-medium">Market Outlook</legend><div className="grid gap-2 sm:grid-cols-3">{outlooks.map((item) => <button key={item.value} type="button" aria-pressed={outlook === item.value} className={cn("rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", outlook === item.value && "border-primary bg-primary/10")} onClick={() => { setOutlook(item.value); setPlan(null); setScenario(null); onProgress(1) }}><strong className="text-sm">{item.label}</strong><span className="mt-1 block text-[10px] leading-4 text-muted-foreground">{item.note}</span></button>)}</div></fieldset>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><label className="space-y-1.5 text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><CalendarDays className="size-3" />Target Date / Horizon</span><Input aria-label="Option planning target date" type="date" min={new Date().toISOString().slice(0, 10)} value={targetDate} onChange={(event) => setTargetDate(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Optional Target Price</span><Input aria-label="Option planning target price" type="number" min="0.01" step="0.01" placeholder="e.g. 240" value={targetPrice} onChange={(event) => setTargetPrice(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Maximum Acceptable Loss</span><Input aria-label="Maximum acceptable option loss" type="number" min="1" step="100" placeholder="Optional" value={maximumLoss} onChange={(event) => setMaximumLoss(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Capital Budget</span><Input aria-label="Option capital budget" type="number" min="1" step="100" placeholder="Optional" value={capitalBudget} onChange={(event) => setCapitalBudget(event.target.value)} /></label></div>
        <details className="rounded-lg border px-4 py-3"><summary className="cursor-pointer text-sm font-medium"><SlidersHorizontal className="mr-2 inline size-4 text-primary" />Ownership And Target Range</summary><div className="mt-4 grid gap-3 sm:grid-cols-3"><label className="space-y-1.5 text-xs text-muted-foreground"><span>Shares Already Owned</span><Input aria-label="Shares already owned" type="number" min="0" step="1" value={sharesOwned} onChange={(event) => setSharesOwned(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Target Range Low</span><Input aria-label="Option target range low" type="number" min="0.01" step="0.01" value={targetPriceLow} onChange={(event) => setTargetPriceLow(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Target Range High</span><Input aria-label="Option target range high" type="number" min="0.01" step="0.01" value={targetPriceHigh} onChange={(event) => setTargetPriceHigh(event.target.value)} /></label><button type="button" aria-pressed={acquiringShares} className={cn("rounded-lg border p-3 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:col-span-3", acquiringShares && "border-primary bg-primary/10")} onClick={() => setAcquiringShares((value) => !value)}><strong className="block text-sm">Acquiring Shares Is Acceptable</strong><span className="mt-1 block text-muted-foreground">Allows the planner to compare a cash-secured put and its assignment obligation.</span></button></div></details>
        <div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-2xl text-xs leading-5 text-muted-foreground"><ShieldCheck className="mr-1 inline size-3.5 text-primary" />The normal planner never suggests an uncovered short call. No structure is labelled objectively best.</p><Button type="button" size="lg" onClick={() => void buildPlan()} disabled={planning || !targetDate}>{planning ? <LoaderCircle className="motion-safe:animate-spin" /> : <BarChart3 />}{planning ? "Building Comparison…" : "Compare Structures"}</Button></div>
      </CardContent></Card>

    {plan && <section aria-labelledby="option-comparison-title" className="space-y-3"><div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><p className="font-mono text-[9px] uppercase tracking-[0.16em] text-primary">2 · Compare</p><h2 id="option-comparison-title" className="mt-1 text-xl font-semibold">Different trade-offs for the same outlook.</h2><p className="mt-1 text-xs text-muted-foreground">{plan.ticker} at {money(plan.underlyingPrice)} · {plan.expiration} expiry · {plan.dataProvenance.source || "Public Data"} · {plan.dataProvenance.status || "Delayed"}</p></div><Badge variant="secondary">{plan.candidates.length} Validated Structures</Badge></div>
      {plan.warnings.map((warning) => <Alert key={warning}><AlertTitle>Planning Context</AlertTitle><AlertDescription>{warning}</AlertDescription></Alert>)}
      <div className="grid min-w-0 gap-3 lg:grid-cols-3">{plan.candidates.map((candidate) => <CandidateCard key={candidate.candidateId} candidate={candidate} selected={selected?.candidateId === candidate.candidateId} onSelect={() => { setSelectedId(candidate.candidateId); setScenario(null); onProgress(2) }} onUse={() => onUseCandidate(candidate)} />)}</div>
      {(plan.earningsContext || plan.impliedMoveContext) && <Card className="gap-3 py-4"><CardHeader className="px-4 sm:px-5"><CardTitle className="text-sm">Event-Move Context</CardTitle><CardDescription>Descriptive context only—not a forecast or evidence of option mispricing.</CardDescription></CardHeader><CardContent className="grid gap-3 px-4 sm:grid-cols-2 sm:px-5">{plan.earningsContext && <div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">HISTORICAL MEDIAN ABSOLUTE EARNINGS MOVE</span><strong className="mt-1 block text-lg">{plan.earningsContext.historicalMedianAbsoluteMovePercent == null ? "Unavailable" : `${plan.earningsContext.historicalMedianAbsoluteMovePercent.toFixed(2)}%`}</strong><p className="mt-1 text-[10px] leading-4 text-muted-foreground">{plan.earningsContext.sampleSize} SEC filing events · as of {new Date(plan.earningsContext.asOf).toLocaleDateString()} · {plan.earningsContext.eventSource} + {plan.earningsContext.priceSource}</p></div>}{plan.impliedMoveContext && <div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">SELECTED-EXPIRY ATM STRADDLE MOVE</span><strong className="mt-1 block text-lg">{plan.impliedMoveContext.movePercent.toFixed(2)}%</strong><p className="mt-1 text-[10px] leading-4 text-muted-foreground">{plan.impliedMoveContext.expiration} · ${plan.impliedMoveContext.strike} strike · {plan.impliedMoveContext.quoteMethod}. {plan.impliedMoveContext.interpretation}</p></div>}</CardContent></Card>}
    </section>}

    {selected && <Card className="border-chart-2/30"><CardHeader><div className="flex items-start gap-3"><span className="grid size-8 shrink-0 place-items-center rounded-full bg-chart-2/15 font-mono text-xs text-chart-2">3</span><div><CardTitle>What if {plan?.ticker} is $X on date Y?</CardTitle><CardDescription className="mt-1.5">Server-side American-option pricing for the selected {selected.name}. Change the candidate above to compare another structure.</CardDescription></div></div></CardHeader><CardContent className="space-y-4"><div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"><label className="space-y-1.5 text-xs text-muted-foreground"><span>Scenario Price</span><Input aria-label="Option scenario price" type="number" min="0.01" step="0.01" value={scenarioPrice} onChange={(event) => setScenarioPrice(event.target.value)} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Scenario Date</span><Input aria-label="Option scenario date" type="date" min={new Date().toISOString().slice(0, 10)} value={scenarioDate} onChange={(event) => setScenarioDate(event.target.value)} /></label><Button type="button" onClick={() => void modelScenario()} disabled={scenarioLoading}>{scenarioLoading ? <LoaderCircle className="motion-safe:animate-spin" /> : <ArrowRight />}{scenarioLoading ? "Modeling…" : "Model Scenario"}</Button></div>{scenario && <div aria-live="polite" className="space-y-3"><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">MODELED POSITION VALUE</span><strong className="mt-1 block text-lg">{money(scenario.modeledPositionValue)}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">MODELED P&L</span><strong className={cn("mt-1 block text-lg", scenario.pnl < 0 ? "text-destructive" : "text-primary")}>{money(scenario.pnl)}{scenario.pnlPercent == null ? "" : ` · ${scenario.pnlPercent.toFixed(2)}%`}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">REMAINING TIME</span><strong className="mt-1 block text-lg">{scenario.remainingDays} Days</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">KEY GREEKS</span><strong className="mt-1 block font-mono text-xs">Δ {scenario.greeks.delta.toFixed(2)} · Θ {scenario.greeks.theta.toFixed(2)}</strong><span className="mt-1 block font-mono text-[10px] text-muted-foreground">Γ {scenario.greeks.gamma.toFixed(2)} · V {scenario.greeks.vega.toFixed(2)}</span></div></div><p className="rounded-lg border bg-muted/25 p-3 text-xs leading-5">{scenario.breakEvenRelation}</p><p className="text-[10px] leading-4 text-muted-foreground">{scenario.assumptions.model} · IV {scenario.assumptions.impliedVolatilities.map((value) => `${value.toFixed(1)}%`).join(" / ")} · rate {(scenario.assumptions.interestRate * 100).toFixed(2)}% · dividend {(scenario.assumptions.dividendYield * 100).toFixed(2)}%</p>{scenario.warnings.map((warning) => <p key={warning} className="text-[10px] leading-4 text-muted-foreground">• {warning}</p>)}</div>}</CardContent></Card>}
  </section>
}
