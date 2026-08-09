import { useEffect, useMemo, useState } from "react"
import { ArrowRight, BookOpenCheck, CircleDollarSign, FileClock, LockKeyhole, Save } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { OptionLifecycleEvent, OptionLifecycleEventType, OptionPositionCreate, OptionPositionResponse, OptionSimulationResult, OptionType, PositionSide } from "@/lib/types"

const eventLabels: Record<OptionLifecycleEventType, string> = {
  hold: "Record Hold Observation",
  close: "Close Selected Leg",
  partial_close: "Partially Close",
  roll_strike: "Roll Strike",
  roll_expiry: "Roll Expiry",
  exercise: "Exercise Long Option",
  expire: "Allow Out-Of-Money Expiry",
  early_assignment: "Simulate Early Assignment",
  expiry_assignment: "Simulate Expiry Assignment",
  buy_shares: "Buy Shares",
  sell_shares: "Sell Shares",
  add_leg: "Add Option Leg",
}

function money(value: number) {
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
}

function numericValue(value: string, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function LifecycleWorkspace({
  draft,
  simulation,
  ledger,
  creating,
  applying,
  onDraftChange,
  onCreate,
  onApply,
}: {
  draft: OptionPositionCreate
  simulation: OptionSimulationResult | null
  ledger: OptionPositionResponse | null
  creating: boolean
  applying: boolean
  onDraftChange: (draft: OptionPositionCreate) => void
  onCreate: () => Promise<void>
  onApply: (event: OptionLifecycleEvent) => Promise<boolean>
}) {
  const [eventOpen, setEventOpen] = useState(false)
  const [eventType, setEventType] = useState<OptionLifecycleEventType>("hold")
  const openLegs = useMemo(() => ledger?.position.legs.filter((leg) => (ledger.position.closed_quantities[leg.leg_id] || 0) < leg.quantity) || [], [ledger])
  const eligibleLegs = useMemo(() => eventType === "exercise" ? openLegs.filter((leg) => leg.side === "long") : ["early_assignment", "expiry_assignment"].includes(eventType) ? openLegs.filter((leg) => leg.side === "short") : openLegs, [eventType, openLegs])
  const [legId, setLegId] = useState("")
  const selectedLeg = eligibleLegs.find((leg) => leg.leg_id === legId) || eligibleLegs[0]
  const [spot, setSpot] = useState(draft.underlying_price)
  const [mark, setMark] = useState(draft.legs[0]?.premium || 0)
  const [quantity, setQuantity] = useState(1)
  const [newStrike, setNewStrike] = useState("")
  const [newExpiration, setNewExpiration] = useState("")
  const [newPremium, setNewPremium] = useState("")
  const [newOptionType, setNewOptionType] = useState<OptionType>("call")
  const [newSide, setNewSide] = useState<PositionSide>("long")
  const [newImpliedVolatility, setNewImpliedVolatility] = useState("30")
  useEffect(() => {
    setSpot(ledger?.position.underlying_price || draft.underlying_price)
    const firstOpenLeg = openLegs[0]
    setLegId(firstOpenLeg?.leg_id || "")
    setMark(firstOpenLeg?.premium || draft.legs[0]?.premium || 0)
  }, [draft.legs, draft.underlying_price, ledger?.position.position_id, ledger?.position.updated_at, openLegs])
  useEffect(() => {
    if (!selectedLeg) return
    setLegId(selectedLeg.leg_id)
    setMark(selectedLeg.premium)
  }, [eventType, selectedLeg])
  const needsLeg = !["hold", "expire", "buy_shares", "sell_shares", "add_leg"].includes(eventType)
  const needsMark = ["close", "partial_close", "roll_strike", "roll_expiry"].includes(eventType)
  const needsQuantity = ["partial_close", "exercise", "early_assignment", "expiry_assignment", "buy_shares", "sell_shares", "add_leg"].includes(eventType)
  const rollIncomplete = eventType === "roll_strike" ? !newStrike || !newPremium : eventType === "roll_expiry" ? !newExpiration || !newPremium : false
  const addLegIncomplete = eventType === "add_leg" && (!newStrike || !newExpiration || !newPremium || !(numericValue(newImpliedVolatility) > 0))
  const applyEvent = async () => {
    const event: OptionLifecycleEvent = {
      event_type: eventType,
      underlying_price: spot,
      option_marks: needsMark && selectedLeg ? { [selectedLeg.leg_id]: mark } : {},
      quantity: needsQuantity ? quantity : null,
      leg_id: needsLeg ? selectedLeg?.leg_id || null : null,
      new_strike: eventType === "roll_strike" && newStrike ? numericValue(newStrike) : null,
      new_expiration: eventType === "roll_expiry" && newExpiration ? newExpiration : null,
      new_premium: ["roll_strike", "roll_expiry"].includes(eventType) && newPremium ? numericValue(newPremium) : null,
      new_leg: eventType === "add_leg" ? {
        leg_id: globalThis.crypto?.randomUUID?.() || `paper-leg-${Date.now()}`,
        option_type: newOptionType,
        side: newSide,
        strike: numericValue(newStrike),
        expiration: newExpiration,
        premium: numericValue(newPremium),
        quantity,
        implied_volatility: numericValue(newImpliedVolatility) / 100,
        multiplier: 100,
        contract_symbol: null,
        premium_source: "manual",
      } : null,
      note: "Paper lifecycle decision from local Option Lab",
    }
    if (await onApply(event)) setEventOpen(false)
  }
  if (!ledger) return <Card id="option-lifecycle" className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><BookOpenCheck className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.15em] text-primary">Paper Lifecycle</span></div><CardTitle>Journal the decisions after entry.</CardTitle><CardDescription className="mt-2 max-w-2xl">Save the simulated structure as a local paper position. Holding, closing, rolling, exercise, expiry, and assignment each preserve a complete DuckDB state snapshot.</CardDescription></div><Badge variant="outline"><LockKeyhole />Local Only</Badge></div></CardHeader><CardContent className="flex flex-col gap-3 border-t pt-5 sm:flex-row sm:items-end"><label className="flex-1 space-y-1.5 text-xs text-muted-foreground"><span>Paper Position Name</span><Input aria-label="Paper position name" value={draft.name} maxLength={100} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} /></label><Button onClick={() => void onCreate()} disabled={!simulation || creating}><Save className={creating ? "motion-safe:animate-pulse" : ""} />{creating ? "Saving Position…" : "Create Paper Position"}</Button></CardContent></Card>

  const position = ledger.position
  return <Card id="option-lifecycle" className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><FileClock className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.15em] text-primary">Paper Lifecycle</span></div><CardTitle>{position.name}</CardTitle><CardDescription className="mt-2 font-mono text-[10px]">Position {position.position_id}{position.research_run_id ? ` · Run ${position.research_run_id}` : ""}</CardDescription></div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{position.current_structure || position.position_kind.replaceAll("_", " ")}</Badge><Badge variant={position.status === "open" ? "default" : "secondary"}>{position.status.toUpperCase()}</Badge><Button disabled={position.status !== "open"} onClick={() => setEventOpen(true)}>Journal Next Decision<ArrowRight /></Button></div></div></CardHeader><CardContent className="space-y-4">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">CASH</span><strong className="mt-1 block">{money(position.cash)}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">SHARES</span><strong className="mt-1 block">{position.shares.toLocaleString()}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">REALIZED P&L</span><strong className={position.realized_pnl < 0 ? "mt-1 block text-destructive" : "mt-1 block text-primary"}>{money(position.realized_pnl)}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">COLLATERAL</span><strong className="mt-1 block">{money(position.collateral)}</strong></div><div className="rounded-lg border p-3"><span className="text-[10px] text-muted-foreground">UNDERLYING</span><strong className="mt-1 block">{money(position.underlying_price)}</strong></div></div>
    <div className="overflow-x-auto"><Table><TableCaption>Every lifecycle event stores its payload and complete resulting position state in local DuckDB.</TableCaption><TableHeader><TableRow><TableHead>#</TableHead><TableHead>Decision</TableHead><TableHead>Structure After</TableHead><TableHead>Recorded</TableHead><TableHead>Status After</TableHead><TableHead>Cash After</TableHead><TableHead>Shares</TableHead><TableHead>Realized P&L</TableHead></TableRow></TableHeader><TableBody>{ledger.events.map((event) => <TableRow key={event.eventId}><TableCell>{event.eventNumber}</TableCell><TableCell>{event.eventType.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</TableCell><TableCell>{event.stateAfter.current_structure || event.stateAfter.position_kind.replaceAll("_", " ")}</TableCell><TableCell>{new Date(event.createdAt).toLocaleString()}</TableCell><TableCell><Badge variant="outline">{event.stateAfter.status}</Badge></TableCell><TableCell>{money(event.stateAfter.cash)}</TableCell><TableCell>{event.stateAfter.shares}</TableCell><TableCell className={event.stateAfter.realized_pnl < 0 ? "text-destructive" : "text-primary"}>{money(event.stateAfter.realized_pnl)}</TableCell></TableRow>)}</TableBody></Table></div>
    <Sheet open={eventOpen} onOpenChange={setEventOpen}><SheetContent className="sm:max-w-md"><SheetHeader className="border-b"><SheetTitle>Journal Next Decision</SheetTitle><SheetDescription>This changes only the local paper ledger. It never submits a brokerage order.</SheetDescription></SheetHeader><div className="space-y-4 px-4">
      <label className="block space-y-1.5 text-sm"><span>Lifecycle Event</span><Select value={eventType} onValueChange={(value: OptionLifecycleEventType) => setEventType(value)}><SelectTrigger aria-label="Lifecycle event" className="w-full"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(eventLabels).map(([value, label]) => <SelectItem key={value} value={value} disabled={value === "exercise" ? !openLegs.some((leg) => leg.side === "long") : ["early_assignment", "expiry_assignment"].includes(value) ? !openLegs.some((leg) => leg.side === "short") : false}>{label}</SelectItem>)}</SelectContent></Select></label>
      {needsLeg && <label className="block space-y-1.5 text-sm"><span>Option Leg</span><Select value={selectedLeg?.leg_id || ""} onValueChange={(value) => { setLegId(value); const leg = eligibleLegs.find((item) => item.leg_id === value); if (leg) setMark(leg.premium) }}><SelectTrigger aria-label="Lifecycle option leg" className="w-full"><SelectValue /></SelectTrigger><SelectContent>{eligibleLegs.map((leg) => <SelectItem key={leg.leg_id} value={leg.leg_id}>{leg.side.toUpperCase()} {leg.option_type.toUpperCase()} · ${leg.strike} · {leg.expiration}</SelectItem>)}</SelectContent></Select></label>}
      <label className="block space-y-1.5 text-sm"><span>Underlying Price At Decision</span><Input aria-label="Lifecycle underlying price" type="number" min="0.01" step="0.01" value={spot} onChange={(event) => setSpot(numericValue(event.target.value))} /></label>
      {needsMark && <label className="block space-y-1.5 text-sm"><span>Current Option Mark</span><Input aria-label="Current option mark" type="number" min="0" step="0.01" value={mark} onChange={(event) => setMark(numericValue(event.target.value))} /></label>}
      {needsQuantity && <label className="block space-y-1.5 text-sm"><span>{["buy_shares", "sell_shares"].includes(eventType) ? "Shares" : "Contracts"}</span><Input aria-label={["buy_shares", "sell_shares"].includes(eventType) ? "Lifecycle share quantity" : "Lifecycle contract quantity"} type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(numericValue(event.target.value, 1))} /></label>}
      {eventType === "roll_strike" && <label className="block space-y-1.5 text-sm"><span>Replacement Strike</span><Input aria-label="Replacement strike" type="number" min="0.01" step="0.5" value={newStrike} onChange={(event) => setNewStrike(event.target.value)} /></label>}
      {eventType === "roll_expiry" && <label className="block space-y-1.5 text-sm"><span>Replacement Expiration</span><Input aria-label="Replacement expiration" type="date" value={newExpiration} onChange={(event) => setNewExpiration(event.target.value)} /></label>}
      {["roll_strike", "roll_expiry"].includes(eventType) && <label className="block space-y-1.5 text-sm"><span>Replacement Premium</span><Input aria-label="Replacement premium" type="number" min="0" step="0.01" value={newPremium} onChange={(event) => setNewPremium(event.target.value)} /></label>}
      {eventType === "add_leg" && <div className="space-y-4 rounded-lg border p-3"><div className="grid grid-cols-2 gap-3"><label className="space-y-1.5 text-sm"><span>Side</span><Select value={newSide} onValueChange={(value: PositionSide) => setNewSide(value)}><SelectTrigger aria-label="New option side" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="long">Long</SelectItem><SelectItem value="short">Short</SelectItem></SelectContent></Select></label><label className="space-y-1.5 text-sm"><span>Type</span><Select value={newOptionType} onValueChange={(value: OptionType) => setNewOptionType(value)}><SelectTrigger aria-label="New option type" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="call">Call</SelectItem><SelectItem value="put">Put</SelectItem></SelectContent></Select></label></div><label className="block space-y-1.5 text-sm"><span>Strike</span><Input aria-label="New leg strike" type="number" min="0.01" step="0.5" value={newStrike} onChange={(event) => setNewStrike(event.target.value)} /></label><label className="block space-y-1.5 text-sm"><span>Expiration</span><Input aria-label="New leg expiration" type="date" value={newExpiration} onChange={(event) => setNewExpiration(event.target.value)} /></label><label className="block space-y-1.5 text-sm"><span>Premium</span><Input aria-label="New leg premium" type="number" min="0" step="0.01" value={newPremium} onChange={(event) => setNewPremium(event.target.value)} /></label><label className="block space-y-1.5 text-sm"><span>Implied Volatility (%)</span><Input aria-label="New leg implied volatility" type="number" min="0.01" max="500" step="0.5" value={newImpliedVolatility} onChange={(event) => setNewImpliedVolatility(event.target.value)} /></label></div>}
      <div className="rounded-lg border border-chart-3/30 bg-chart-3/5 p-3 text-xs leading-5 text-muted-foreground"><CircleDollarSign className="mr-1 inline size-3 text-chart-3" />Use an observed or explicitly assumed current mark. The free provider does not reconstruct historical contract marks.</div>
    </div><SheetFooter className="border-t"><Button onClick={() => void applyEvent()} disabled={applying || (needsLeg && !selectedLeg) || rollIncomplete || addLegIncomplete}>{applying ? "Applying Event…" : "Apply Paper Event"}</Button></SheetFooter></SheetContent></Sheet>
  </CardContent></Card>
}
