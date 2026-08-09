import { useEffect, useMemo, useState } from "react"
import { BookOpen, Check, Database, Layers3, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { optionContractPremium, optionContractPremiumSource, optionPositionDescription } from "@/features/option-lab/option-presets"
import type { OptionChainContract, OptionChainResponse, OptionLeg, OptionPositionCreate, OptionPositionTemplate } from "@/lib/types"
import { cn } from "@/lib/utils"

function numericValue(value: string, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function sortedContracts(contracts: OptionChainContract[]) {
  return [...contracts].sort((first, second) => first.strike - second.strike)
}

function daysToExpiry(expiration: string) {
  const milliseconds = new Date(`${expiration}T00:00:00`).getTime() - new Date().setHours(0, 0, 0, 0)
  return Math.max(Math.ceil(milliseconds / 86_400_000), 0)
}

function recipeCategory(template: OptionPositionTemplate) {
  if (template.category) return template.category
  if (["long_call", "long_put"].includes(template.kind)) return "Directional"
  if (["short_call", "short_put", "covered_call", "cash_secured_put"].includes(template.kind)) return "Income"
  if (template.kind === "conversion") return "Financing / Parity"
  return "Defined Risk"
}

function ContractList({ contracts, targetSide, onSelect }: { contracts: OptionChainContract[]; targetSide: "long" | "short"; onSelect: (contract: OptionChainContract) => void }) {
  if (!contracts.length) return <div className="grid h-48 place-items-center text-sm text-muted-foreground">No contracts were returned for this side.</div>
  return <div className="min-w-[860px]"><div className="grid grid-cols-[.8fr_.8fr_1.15fr_1fr_.8fr_1fr_.8fr] gap-2 border-b px-3 py-2 font-mono text-[9px] uppercase text-muted-foreground"><span>Strike</span><span>Last</span><span>Bid / Ask</span><span>{targetSide === "long" ? "Buy At" : "Sell At"}</span><span>Spread</span><span>Volume / OI</span><span>IV</span></div>{contracts.map((contract) => { const executionPrice = optionContractPremium(contract, targetSide); const executionSource = optionContractPremiumSource(contract, targetSide); return <button type="button" key={contract.contract} title={`${contract.contract} · ${contract.quoteQuality || "Cached Quote"}${contract.lastTradeAt ? ` · last trade ${contract.lastTradeAt}` : ""}`} className="grid w-full grid-cols-[.8fr_.8fr_1.15fr_1fr_.8fr_1fr_.8fr] gap-2 border-b px-3 py-3 text-left font-mono text-xs transition-colors hover:bg-primary/10 focus-visible:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary" onClick={() => onSelect(contract)}><strong className={contract.inTheMoney ? "text-primary" : ""}>${contract.strike.toFixed(2)}</strong><span>${contract.last.toFixed(2)}</span><span>${contract.bid.toFixed(2)} / ${contract.ask.toFixed(2)}</span><span className="text-primary">${executionPrice.toFixed(2)} <small className="text-[8px] uppercase text-muted-foreground">{executionSource}</small></span><span>${(contract.spread ?? Math.max(contract.ask - contract.bid, 0)).toFixed(2)}</span><span>{contract.volume.toLocaleString()} / {contract.openInterest.toLocaleString()}</span><span>{contract.iv.toFixed(2)}%</span></button> })}</div>
}

function LegCard({ leg, role, index, onChange, onOpenChain }: { leg: OptionLeg; role?: string; index: number; onChange: (nextLeg: OptionLeg) => void; onOpenChain: () => void }) {
  const updateNumber = (field: "strike" | "premium" | "quantity" | "implied_volatility", value: string) => onChange({ ...leg, [field]: field === "implied_volatility" ? numericValue(value) / 100 : numericValue(value), ...(field === "premium" ? { premium_source: "manual" as const, contract_symbol: null } : {}) })
  return <Card className="gap-4 border-border/80 bg-background/45 py-4"><CardHeader className="px-4 sm:px-5"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><span className="grid size-7 place-items-center rounded-full border font-mono text-[10px] text-muted-foreground">{index + 1}</span><div><CardTitle className="text-base">{role || `${leg.side === "long" ? "Long" : "Short"} ${leg.option_type === "call" ? "Call" : "Put"}`}</CardTitle><span className="text-[10px] text-muted-foreground">{leg.side.toUpperCase()} {leg.option_type.toUpperCase()}</span></div><Badge variant={leg.side === "long" ? "secondary" : "outline"}>{leg.side === "long" ? "Debit" : "Credit"}</Badge></div><Button type="button" size="sm" variant="outline" onClick={onOpenChain}><Search />Choose Contract</Button></div><CardDescription className="truncate">{leg.contract_symbol ? `${leg.contract_symbol} · premium from ${leg.premium_source || "quote"}` : "Manual assumptions · no chain contract selected"}</CardDescription></CardHeader><CardContent className="grid gap-3 px-4 sm:grid-cols-2 sm:px-5 xl:grid-cols-5">
    <label className="space-y-1.5 text-xs text-muted-foreground"><span>Strike</span><Input aria-label={`Leg ${index + 1} strike`} type="number" min="0.01" step="0.5" value={leg.strike} onChange={(event) => updateNumber("strike", event.target.value)} /></label>
    <label className="space-y-1.5 text-xs text-muted-foreground"><span>Premium</span><Input aria-label={`Leg ${index + 1} premium`} type="number" min="0" step="0.01" value={leg.premium} onChange={(event) => updateNumber("premium", event.target.value)} /></label>
    <label className="space-y-1.5 text-xs text-muted-foreground"><span>Implied Volatility</span><div className="relative"><Input aria-label={`Leg ${index + 1} implied volatility`} type="number" min="0.01" max="500" step="0.5" className="pr-8" value={Number((leg.implied_volatility * 100).toFixed(2))} onChange={(event) => updateNumber("implied_volatility", event.target.value)} /><span className="pointer-events-none absolute right-3 top-2 text-xs text-muted-foreground">%</span></div></label>
    <label className="space-y-1.5 text-xs text-muted-foreground"><span>Contracts</span><Input aria-label={`Leg ${index + 1} contracts`} type="number" min="1" max="1000" step="1" value={leg.quantity} onChange={(event) => updateNumber("quantity", event.target.value)} /></label>
    <label className="space-y-1.5 text-xs text-muted-foreground"><span>Expiration</span><Input aria-label={`Leg ${index + 1} expiration`} type="date" value={leg.expiration} onChange={(event) => onChange({ ...leg, expiration: event.target.value, contract_symbol: null })} /></label>
  </CardContent></Card>
}

export function PositionBuilder({
  draft,
  templates,
  chain,
  chainLoading,
  chainError,
  onChange,
  onSelectTemplate,
  onLoadChain,
  onSelectContract,
}: {
  draft: OptionPositionCreate
  templates: OptionPositionTemplate[]
  chain: OptionChainResponse | null
  chainLoading: boolean
  chainError: string
  onChange: (draft: OptionPositionCreate) => void
  onSelectTemplate: (template: OptionPositionTemplate) => void
  onLoadChain: (expiration?: string) => void
  onSelectContract: (legId: string, contract: OptionChainContract, expiration: string) => void
}) {
  const [chainOpen, setChainOpen] = useState(false)
  const [targetLegId, setTargetLegId] = useState<string | null>(null)
  const selectedTemplate = templates.find((template) => template.kind === draft.position_kind)
  const categories = useMemo(() => [...new Set(templates.map(recipeCategory))], [templates])
  const [selectedCategory, setSelectedCategory] = useState(() => selectedTemplate ? recipeCategory(selectedTemplate) : "Directional")
  useEffect(() => {
    if (selectedTemplate) setSelectedCategory(recipeCategory(selectedTemplate))
  }, [selectedTemplate])
  const targetLeg = draft.legs.find((leg) => leg.leg_id === targetLegId) || draft.legs[0]
  const calls = useMemo(() => sortedContracts(chain?.calls || []), [chain])
  const puts = useMemo(() => sortedContracts(chain?.puts || []), [chain])
  const updateLeg = (nextLeg: OptionLeg) => {
    const legs = draft.legs.map((leg) => leg.leg_id === nextLeg.leg_id ? nextLeg : leg)
    const shortContracts = legs.filter((leg) => leg.side === "short").reduce((total, leg) => total + leg.quantity, 0)
    const shares = draft.position_kind === "covered_call" ? Math.max(draft.shares, shortContracts * 100) : draft.position_kind === "conversion" ? legs[0].quantity * legs[0].multiplier : draft.shares
    onChange({ ...draft, legs, shares })
  }
  const chooseContract = (contract: OptionChainContract) => {
    if (!targetLegId || !chain?.expiration) return
    onSelectContract(targetLegId, contract, chain.expiration)
    setChainOpen(false)
  }
  const openChain = (legId: string) => {
    setTargetLegId(legId)
    setChainOpen(true)
    if (!chain && !chainLoading) onLoadChain()
  }
  return <section aria-labelledby="position-recipe-title" className="space-y-4">
    <Card className="gap-4 py-5"><CardHeader className="px-4 sm:px-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Layers3 className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.15em] text-primary">Position Recipe V2</span></div><CardTitle id="position-recipe-title" className="text-xl">Choose the obligation you want to study.</CardTitle><CardDescription className="mt-2 max-w-3xl">Recipes now declare capital shape, risk, and required leg relationships before you select contracts.</CardDescription></div><Badge variant="outline">{templates.length} research recipes</Badge></div></CardHeader><CardContent className="space-y-4 px-4 sm:px-6"><div role="tablist" aria-label="Position recipe categories" className="flex gap-1 overflow-x-auto rounded-lg border bg-background/40 p-1">{categories.map((category) => <button role="tab" type="button" key={category} aria-selected={selectedCategory === category} className={cn("shrink-0 rounded-md px-3 py-2 text-xs text-muted-foreground", selectedCategory === category && "bg-primary/10 text-primary")} onClick={() => setSelectedCategory(category)}>{category}</button>)}</div><div role="list" aria-label={`${selectedCategory} option position recipes`} className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{templates.filter((template) => recipeCategory(template) === selectedCategory).map((template) => { const selected = template.kind === draft.position_kind; return <div role="listitem" key={template.kind}><button type="button" aria-pressed={selected} className={cn("h-full w-full rounded-lg border p-3 text-left transition-all hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", selected && "border-primary/60 bg-primary/10")} onClick={() => onSelectTemplate(template)}><span className="flex items-center justify-between gap-3"><strong className="text-sm">{template.name}</strong>{selected && <Check className="size-4 text-primary" />}</span><span className="mt-2 block text-[10px] leading-4 text-muted-foreground">{template.description || optionPositionDescription(template.kind)}</span><span className={cn("mt-3 inline-flex rounded-full border px-2 py-0.5 font-mono text-[8px] uppercase", template.riskLabel?.toLowerCase().includes("uncapped") && "border-destructive/50 text-destructive")}>{template.riskLabel || "Inspect Risk"}</span></button></div> })}</div>{selectedTemplate && <div className="grid gap-2 rounded-lg border bg-background/50 p-3 sm:grid-cols-2 xl:grid-cols-4"><div><span className="font-mono text-[8px] text-muted-foreground">CAPITAL</span><strong className="mt-1 block text-xs">{selectedTemplate.capitalProfile || "Structure Dependent"}</strong></div><div><span className="font-mono text-[8px] text-muted-foreground">RISK</span><strong className={cn("mt-1 block text-xs", selectedTemplate.riskLabel?.toLowerCase().includes("uncapped") && "text-destructive")}>{selectedTemplate.riskLabel || "Review Payoff"}</strong></div><div><span className="font-mono text-[8px] text-muted-foreground">EXPIRY RULE</span><strong className="mt-1 block text-xs">{selectedTemplate.expiryPolicy || "One Selected Expiry"}</strong></div><div><span className="font-mono text-[8px] text-muted-foreground">STRIKE RULE</span><strong className="mt-1 block text-xs">{selectedTemplate.strikePolicy || "User Selected"}</strong></div></div>}</CardContent></Card>
    <div className="space-y-3">{draft.legs.map((leg, index) => <LegCard key={leg.leg_id} leg={leg} role={selectedTemplate?.legs[index]?.role} index={index} onChange={updateLeg} onOpenChain={() => openChain(leg.leg_id)} />)}</div>
    {["covered_call", "conversion"].includes(draft.position_kind) && <Card className="gap-3 py-4"><CardContent className="flex flex-col gap-3 px-4 sm:flex-row sm:items-center sm:px-5"><div className="flex-1"><strong className="text-sm">{draft.position_kind === "conversion" ? "Matched Share Leg" : "Share Cover"}</strong><p className="mt-1 text-xs text-muted-foreground">{draft.position_kind === "conversion" ? "Conversion requires exactly 100 shares per matched put/call pair." : "Shares cover the short-call delivery obligation."} No brokerage order is sent.</p></div><label className="space-y-1.5 text-xs text-muted-foreground"><span>Shares</span><Input aria-label="Covered shares" className="w-32" type="number" min="0" step="100" value={draft.shares} disabled={draft.position_kind === "conversion"} onChange={(event) => onChange({ ...draft, shares: numericValue(event.target.value), share_cost_basis: draft.underlying_price })} /></label><label className="space-y-1.5 text-xs text-muted-foreground"><span>Share Cost Basis</span><Input aria-label="Share cost basis" className="w-36" type="number" min="0.01" step="0.01" value={draft.share_cost_basis || draft.underlying_price} onChange={(event) => onChange({ ...draft, share_cost_basis: numericValue(event.target.value) })} /></label></CardContent></Card>}
    <Card className="gap-3 border-dashed py-4"><CardContent className="flex flex-wrap items-center gap-3 px-4 sm:px-5"><Database className="size-4 text-primary" /><div className="min-w-56 flex-1"><strong className="text-sm">Current Chain Snapshot</strong><p className="mt-1 text-xs text-muted-foreground">{chain?.expiration ? `${draft.ticker} · ${chain.expiration} · ${chain.dataStatus?.status || "Delayed"}` : chainError || "Load public data to inspect strikes, bid/ask, open interest, and IV."}</p></div><Button type="button" variant="outline" onClick={() => { setTargetLegId(draft.legs[0]?.leg_id || null); setChainOpen(true); if (!chain) onLoadChain() }} disabled={chainLoading}>{chainLoading ? "Loading Chain…" : chain ? "Inspect Chain" : "Load Current Chain"}</Button></CardContent></Card>
    <Sheet open={chainOpen} onOpenChange={setChainOpen}><SheetContent className="w-[min(100vw,960px)] sm:max-w-[960px]"><SheetHeader className="border-b"><SheetTitle>Select A Current Contract</SheetTitle><SheetDescription>Follow the three visible decisions below. Yahoo returns one complete call/put chain for the expiry you select; it is not historical execution data.</SheetDescription></SheetHeader><div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4"><div className="grid gap-2 sm:grid-cols-3"><div className="rounded-lg border bg-primary/5 p-3"><span className="font-mono text-[9px] text-primary">1 · TARGET LEG</span><strong className="mt-1 block text-sm">{targetLeg ? `${targetLeg.side.toUpperCase()} ${targetLeg.option_type.toUpperCase()}` : "Choose A Leg"}</strong></div><div className="rounded-lg border bg-primary/5 p-3"><span className="font-mono text-[9px] text-primary">2 · EXPIRY</span><strong className="mt-1 block text-sm">{chain?.expiration ? `${chain.expiration} · ${daysToExpiry(chain.expiration)} DTE` : "Load Available Dates"}</strong></div><div className="rounded-lg border bg-primary/5 p-3"><span className="font-mono text-[9px] text-primary">3 · CONTRACT</span><strong className="mt-1 block text-sm">Inspect All Strikes</strong></div></div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline"><Database />{chain?.source || "Yahoo Finance"}</Badge><Badge variant="secondary">{chain?.historicalStatus || "Current Snapshot"}</Badge>{chain?.dataStatus?.qualityWarnings?.map((warning) => <span key={warning} className="text-[10px] text-muted-foreground">{warning}</span>)}</div>{chain?.expirations.length ? <div><div className="mb-2 flex items-center justify-between gap-2"><span className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground">All Available Expiries</span><span className="text-[10px] text-muted-foreground">{chain.expirations.length} dates</span></div><div className="flex gap-2 overflow-x-auto pb-2">{chain.expirations.map((expiration) => <button type="button" key={expiration} aria-pressed={expiration === chain.expiration} disabled={chainLoading} className={cn("min-w-32 rounded-lg border px-3 py-2 text-left transition-colors hover:border-primary/60 hover:bg-primary/5", expiration === chain.expiration && "border-primary bg-primary/10")} onClick={() => onLoadChain(expiration)}><strong className="block text-xs">{expiration}</strong><span className="font-mono text-[9px] text-muted-foreground">{daysToExpiry(expiration)} DTE</span></button>)}</div></div> : null}{chainLoading ? <div className="grid h-64 place-items-center text-sm text-muted-foreground">Loading every contract for the selected expiry…</div> : chainError ? <div className="grid h-64 place-items-center text-center text-sm text-destructive">{chainError}</div> : <Tabs key={`${targetLegId}-${targetLeg?.option_type}-${chain?.expiration}`} defaultValue={targetLeg?.option_type || "call"}><TabsList><TabsTrigger value="call">Calls · all {calls.length}</TabsTrigger><TabsTrigger value="put">Puts · all {puts.length}</TabsTrigger></TabsList><TabsContent value="call"><ScrollArea className="h-[calc(100vh-430px)] min-h-72 overflow-x-auto"><ContractList contracts={calls} targetSide={targetLeg?.side || "long"} onSelect={chooseContract} /></ScrollArea></TabsContent><TabsContent value="put"><ScrollArea className="h-[calc(100vh-430px)] min-h-72 overflow-x-auto"><ContractList contracts={puts} targetSide={targetLeg?.side || "long"} onSelect={chooseContract} /></ScrollArea></TabsContent></Tabs>}</div><div className="mt-auto border-t p-4 text-xs text-muted-foreground"><BookOpen className="mr-1 inline size-3" />Long legs use the current ask; short legs use the current bid. A labelled last/mid fallback is used only when the corresponding quote side is unavailable.</div></SheetContent></Sheet>
  </section>
}
