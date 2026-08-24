import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react"
import { BriefcaseBusiness, Database, Pencil, Plus, RefreshCw, Save, ShieldCheck, Trash2, WalletCards } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ApiError,
  createPortfolioPosition,
  deletePortfolioPosition,
  loadPortfolioContext,
  savePortfolioContext,
  saveRiskPolicy,
  snapshotRiskPolicy,
  updatePortfolioPosition,
} from "@/lib/api"
import type { PortfolioBundle, PortfolioPosition, PortfolioPositionInput, RiskPolicyInput } from "@/lib/types"

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 })
const emptyContext = { investableValue: "", liquidCash: "" }
const emptyPolicy = {
  name: "",
  normalTarget: "",
  maxSingleName: "",
  maxAssignment: "",
  maxCollateral: "",
  minimumCashPercent: "",
  minimumCashAmount: "",
  stressCeiling: "",
}
const emptyPosition = { ticker: "", shares: "", costBasis: "", manualMarketValue: "", notes: "" }

function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "The local portfolio request failed unexpectedly."
}

function optionalNumber(value: string) {
  return value.trim() ? Number(value) : null
}

function requiredNumber(label: string, value: string, allowZero = false) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || (allowZero ? parsed < 0 : parsed <= 0)) {
    throw new Error(`${label} must be ${allowZero ? "zero or greater" : "greater than zero"}.`)
  }
  return parsed
}

function nonZeroNumber(label: string, value: string) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed === 0) throw new Error(`${label} must be non-zero.`)
  return parsed
}

function reserveLabel(policy: PortfolioBundle["risk_policy"]) {
  if (!policy) return "Not configured"
  const values = []
  if (policy.min_unencumbered_cash_reserve_amount !== null) values.push(currency.format(policy.min_unencumbered_cash_reserve_amount))
  if (policy.min_unencumbered_cash_reserve_percent !== null) values.push(`${policy.min_unencumbered_cash_reserve_percent}%`)
  return values.join(" · ")
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="grid min-w-0 gap-1.5 text-sm"><span className="font-medium">{label}</span>{children}{hint ? <span className="text-xs leading-5 text-muted-foreground">{hint}</span> : null}</label>
}

function RiskPolicySummary({ bundle }: { bundle: PortfolioBundle }) {
  const policy = bundle.risk_policy
  return <div className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3">
    <div className="bg-card p-4"><span className="text-xs text-muted-foreground">Max Position</span><strong className="mt-1 block text-xl">{policy ? `${policy.max_single_name_exposure_percent}%` : "—"}</strong></div>
    <div className="bg-card p-4"><span className="text-xs text-muted-foreground">Min Cash Reserve</span><strong className="mt-1 block text-xl">{reserveLabel(policy)}</strong></div>
    <div className="bg-card p-4"><span className="text-xs text-muted-foreground">Stress Ceiling</span><strong className="mt-1 block text-xl text-destructive">{policy ? `-${policy.portfolio_stress_loss_ceiling_percent}%` : "—"}</strong></div>
  </div>
}

export function PortfolioRiskSheet({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const [bundle, setBundle] = useState<PortfolioBundle>({ context: null, positions: [], risk_policy: null })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [contextForm, setContextForm] = useState(emptyContext)
  const [policyForm, setPolicyForm] = useState(emptyPolicy)
  const [positionForm, setPositionForm] = useState(emptyPosition)
  const [editingPositionId, setEditingPositionId] = useState("")

  const applyBundle = useCallback((next: PortfolioBundle) => {
    setBundle(next)
    setContextForm(next.context ? {
      investableValue: String(next.context.investable_value),
      liquidCash: String(next.context.liquid_cash),
    } : emptyContext)
    setPolicyForm(next.risk_policy ? {
      name: next.risk_policy.name,
      normalTarget: String(next.risk_policy.normal_target_position_percent),
      maxSingleName: String(next.risk_policy.max_single_name_exposure_percent),
      maxAssignment: String(next.risk_policy.max_assignment_exposure_percent),
      maxCollateral: String(next.risk_policy.max_short_option_collateral_percent),
      minimumCashPercent: next.risk_policy.min_unencumbered_cash_reserve_percent === null ? "" : String(next.risk_policy.min_unencumbered_cash_reserve_percent),
      minimumCashAmount: next.risk_policy.min_unencumbered_cash_reserve_amount === null ? "" : String(next.risk_policy.min_unencumbered_cash_reserve_amount),
      stressCeiling: String(next.risk_policy.portfolio_stress_loss_ceiling_percent),
    } : emptyPolicy)
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      applyBundle(await loadPortfolioContext())
      setError("")
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }, [applyBundle])

  useEffect(() => {
    if (open) void refresh()
  }, [open, refresh])

  const submitContext = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const context = await savePortfolioContext({
        investable_value: requiredNumber("Investable portfolio value", contextForm.investableValue, true),
        liquid_cash: requiredNumber("Liquid cash", contextForm.liquidCash, true),
        base_currency: "USD",
      })
      setBundle((current) => ({ ...current, context }))
      toast.success("Portfolio context saved locally.")
    } catch (requestError) {
      toast.error("Portfolio context was not saved", { description: errorMessage(requestError) })
    } finally {
      setSaving(false)
    }
  }

  const submitPolicy = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const request: RiskPolicyInput = {
        name: policyForm.name.trim(),
        normal_target_position_percent: requiredNumber("Normal target position", policyForm.normalTarget),
        max_single_name_exposure_percent: requiredNumber("Maximum single-name exposure", policyForm.maxSingleName),
        max_assignment_exposure_percent: requiredNumber("Maximum assignment exposure", policyForm.maxAssignment),
        max_short_option_collateral_percent: requiredNumber("Maximum short-option collateral", policyForm.maxCollateral),
        min_unencumbered_cash_reserve_percent: optionalNumber(policyForm.minimumCashPercent),
        min_unencumbered_cash_reserve_amount: optionalNumber(policyForm.minimumCashAmount),
        portfolio_stress_loss_ceiling_percent: requiredNumber("Portfolio stress-loss ceiling", policyForm.stressCeiling),
      }
      if (!request.name) throw new Error("Risk policy name is required.")
      if (request.min_unencumbered_cash_reserve_percent === null && request.min_unencumbered_cash_reserve_amount === null) {
        throw new Error("Define the minimum cash reserve as a percentage, an amount, or both.")
      }
      const riskPolicy = await saveRiskPolicy(request)
      setBundle((current) => ({ ...current, risk_policy: riskPolicy }))
      toast.success(`Risk policy version ${riskPolicy.version} saved.`)
    } catch (requestError) {
      toast.error("Risk policy was not saved", { description: errorMessage(requestError) })
    } finally {
      setSaving(false)
    }
  }

  const submitPosition = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const request: PortfolioPositionInput = {
        ticker: positionForm.ticker.trim().toUpperCase(),
        shares: nonZeroNumber("Shares", positionForm.shares),
        cost_basis_per_share: requiredNumber("Cost basis per share", positionForm.costBasis, true),
        manual_market_value: optionalNumber(positionForm.manualMarketValue),
        notes: positionForm.notes.trim(),
      }
      if (!request.ticker) throw new Error("Ticker is required.")
      if (editingPositionId) await updatePortfolioPosition(editingPositionId, request)
      else await createPortfolioPosition(request)
      setPositionForm(emptyPosition)
      setEditingPositionId("")
      await refresh()
      toast.success(editingPositionId ? "Holding updated." : "Holding added.")
    } catch (requestError) {
      toast.error("Holding was not saved", { description: errorMessage(requestError) })
    } finally {
      setSaving(false)
    }
  }

  const editPosition = (position: PortfolioPosition) => {
    setEditingPositionId(position.position_id)
    setPositionForm({
      ticker: position.ticker,
      shares: String(position.shares),
      costBasis: String(position.cost_basis_per_share),
      manualMarketValue: position.manual_market_value === null ? "" : String(position.manual_market_value),
      notes: position.notes,
    })
  }

  const removePosition = async (position: PortfolioPosition) => {
    if (!window.confirm(`Remove ${position.ticker} from the manual portfolio context?`)) return
    setSaving(true)
    try {
      await deletePortfolioPosition(position.position_id)
      await refresh()
      toast.success(`${position.ticker} removed from portfolio context.`)
    } catch (requestError) {
      toast.error("Holding was not removed", { description: errorMessage(requestError) })
    } finally {
      setSaving(false)
    }
  }

  const snapshot = async () => {
    setSaving(true)
    try {
      const result = await snapshotRiskPolicy()
      toast.success(`Policy v${result.policy_version} snapshot created.`, { description: `Snapshot ${result.snapshot_id.slice(0, 8)} is ready for a future decision record.` })
    } catch (requestError) {
      toast.error("Risk-policy snapshot was not created", { description: errorMessage(requestError) })
    } finally {
      setSaving(false)
    }
  }

  return <Sheet open={open} onOpenChange={setOpen}>
    <SheetTrigger asChild><Button variant="outline" size={compact ? "icon" : "sm"} className={compact ? "shrink-0" : "w-full justify-start"}><ShieldCheck /><span className={compact ? "sr-only" : ""}>Portfolio &amp; Risk</span></Button></SheetTrigger>
    <SheetContent className="w-[min(100vw,720px)] sm:max-w-[720px]">
      <SheetHeader className="border-b pr-12"><div className="flex flex-wrap items-center gap-2"><SheetTitle>Portfolio &amp; Risk</SheetTitle><Badge variant="outline">Local Only</Badge>{bundle.risk_policy ? <Badge variant="secondary">Policy v{bundle.risk_policy.version}</Badge> : null}</div><SheetDescription>Set desired portfolio limits before choosing shares, strategies, or option contracts. These settings do not place orders or recommend trades.</SheetDescription></SheetHeader>
      <div className="px-4"><RiskPolicySummary bundle={bundle} /></div>
      {error ? <Alert variant="destructive" className="mx-4"><Database /><AlertTitle>Local Portfolio Context Unavailable</AlertTitle><AlertDescription><p>{error}</p><Button className="mt-3" size="sm" variant="outline" onClick={() => void refresh()}><RefreshCw />Try Again</Button></AlertDescription></Alert> : null}
      <ScrollArea className="min-h-0 flex-1 px-4">
        {loading ? <div className="grid min-h-72 place-items-center text-sm text-muted-foreground"><RefreshCw className="mr-2 inline size-4 motion-safe:animate-spin" />Loading local portfolio context…</div> : <Tabs defaultValue="capital" className="pb-8">
          <TabsList className="w-full"><TabsTrigger value="capital"><WalletCards />Capital</TabsTrigger><TabsTrigger value="policy"><ShieldCheck />Risk Policy</TabsTrigger><TabsTrigger value="holdings"><BriefcaseBusiness />Holdings <Badge variant="secondary">{bundle.positions.length}</Badge></TabsTrigger></TabsList>
          <TabsContent value="capital" className="space-y-5 pt-4"><div><h3 className="font-semibold">Investable Portfolio Context</h3><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Liquid cash is a subset of investable value. Both remain manual and survive market-data failures.</p></div><form className="grid gap-4 sm:grid-cols-2" onSubmit={(event) => void submitContext(event)}><Field label="Investable Value" hint="Total capital you permit this research workspace to consider."><Input aria-label="Investable value" type="number" min="0" step="0.01" inputMode="decimal" value={contextForm.investableValue} onChange={(event) => setContextForm((current) => ({ ...current, investableValue: event.target.value }))} required /></Field><Field label="Liquid Cash" hint="Cash currently available before reserves or collateral."><Input aria-label="Liquid cash" type="number" min="0" step="0.01" inputMode="decimal" value={contextForm.liquidCash} onChange={(event) => setContextForm((current) => ({ ...current, liquidCash: event.target.value }))} required /></Field><div className="sm:col-span-2"><Button type="submit" disabled={saving}><Save />Save Capital Context</Button></div></form></TabsContent>
          <TabsContent value="policy" className="space-y-5 pt-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Personal Risk Policy</h3><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Saving creates a new immutable version. Percentages are explicit personal limits, not platform defaults.</p></div><Button variant="outline" size="sm" disabled={saving || !bundle.risk_policy} onClick={() => void snapshot()}><Database />Create Snapshot</Button></div><form className="grid gap-4 sm:grid-cols-2" onSubmit={(event) => void submitPolicy(event)}><div className="sm:col-span-2"><Field label="Policy Name"><Input aria-label="Policy name" maxLength={120} value={policyForm.name} onChange={(event) => setPolicyForm((current) => ({ ...current, name: event.target.value }))} required /></Field></div><Field label="Normal Target Position %"><Input aria-label="Normal target position percent" type="number" min="0.01" max="100" step="0.01" inputMode="decimal" value={policyForm.normalTarget} onChange={(event) => setPolicyForm((current) => ({ ...current, normalTarget: event.target.value }))} required /></Field><Field label="Maximum Single-Name Exposure %"><Input aria-label="Maximum single-name exposure percent" type="number" min="0.01" max="100" step="0.01" inputMode="decimal" value={policyForm.maxSingleName} onChange={(event) => setPolicyForm((current) => ({ ...current, maxSingleName: event.target.value }))} required /></Field><Field label="Maximum Assignment Exposure %"><Input aria-label="Maximum assignment exposure percent" type="number" min="0.01" max="100" step="0.01" inputMode="decimal" value={policyForm.maxAssignment} onChange={(event) => setPolicyForm((current) => ({ ...current, maxAssignment: event.target.value }))} required /></Field><Field label="Maximum Short-Option Collateral %"><Input aria-label="Maximum short-option collateral percent" type="number" min="0.01" max="100" step="0.01" inputMode="decimal" value={policyForm.maxCollateral} onChange={(event) => setPolicyForm((current) => ({ ...current, maxCollateral: event.target.value }))} required /></Field><Field label="Minimum Cash Reserve %" hint="Optional when an amount is supplied."><Input aria-label="Minimum cash reserve percent" type="number" min="0" max="100" step="0.01" inputMode="decimal" value={policyForm.minimumCashPercent} onChange={(event) => setPolicyForm((current) => ({ ...current, minimumCashPercent: event.target.value }))} /></Field><Field label="Minimum Cash Reserve Amount" hint="Optional when a percentage is supplied."><Input aria-label="Minimum cash reserve amount" type="number" min="0" step="0.01" inputMode="decimal" value={policyForm.minimumCashAmount} onChange={(event) => setPolicyForm((current) => ({ ...current, minimumCashAmount: event.target.value }))} /></Field><Field label="Portfolio Stress-Loss Ceiling %" hint="Enter the positive loss magnitude; the summary displays it as negative."><Input aria-label="Portfolio stress-loss ceiling percent" type="number" min="0.01" max="100" step="0.01" inputMode="decimal" value={policyForm.stressCeiling} onChange={(event) => setPolicyForm((current) => ({ ...current, stressCeiling: event.target.value }))} required /></Field><div className="flex items-end"><Button type="submit" disabled={saving}><Save />Save New Policy Version</Button></div></form></TabsContent>
          <TabsContent value="holdings" className="space-y-5 pt-4"><div><h3 className="font-semibold">Manual Existing Positions</h3><p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Ticker identity resolves locally where possible. Manual shares, cost basis, and value remain stored even without a live quote.</p></div>{!bundle.context ? <Alert><WalletCards /><AlertTitle>Capital Context Required</AlertTitle><AlertDescription>Save investable value and liquid cash before adding holdings.</AlertDescription></Alert> : <form className="grid gap-4 rounded-lg border bg-card/40 p-4 sm:grid-cols-2" onSubmit={(event) => void submitPosition(event)}><Field label="Ticker"><Input aria-label="Holding ticker" maxLength={12} value={positionForm.ticker} onChange={(event) => setPositionForm((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))} required /></Field><Field label="Shares" hint="Negative shares may represent a manual short-stock position."><Input aria-label="Holding shares" type="number" step="0.0001" inputMode="decimal" value={positionForm.shares} onChange={(event) => setPositionForm((current) => ({ ...current, shares: event.target.value }))} required /></Field><Field label="Cost Basis Per Share"><Input aria-label="Holding cost basis per share" type="number" min="0" step="0.01" inputMode="decimal" value={positionForm.costBasis} onChange={(event) => setPositionForm((current) => ({ ...current, costBasis: event.target.value }))} required /></Field><Field label="Manual Market Value" hint="Optional signed override used when a live price is unavailable."><Input aria-label="Holding manual market value" type="number" step="0.01" inputMode="decimal" value={positionForm.manualMarketValue} onChange={(event) => setPositionForm((current) => ({ ...current, manualMarketValue: event.target.value }))} /></Field><div className="sm:col-span-2"><Field label="Notes"><Input aria-label="Holding notes" maxLength={1000} value={positionForm.notes} onChange={(event) => setPositionForm((current) => ({ ...current, notes: event.target.value }))} /></Field></div><div className="flex flex-wrap gap-2 sm:col-span-2"><Button type="submit" disabled={saving}>{editingPositionId ? <Save /> : <Plus />}{editingPositionId ? "Update Holding" : "Add Holding"}</Button>{editingPositionId ? <Button type="button" variant="ghost" onClick={() => { setEditingPositionId(""); setPositionForm(emptyPosition) }}>Cancel Edit</Button> : null}</div></form>}<div className="space-y-2">{bundle.positions.length ? bundle.positions.map((position) => <article key={position.position_id} className="rounded-lg border p-4"><div className="flex min-w-0 flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><strong>{position.ticker}</strong><Badge variant={position.identity_status === "resolved" ? "secondary" : "outline"}>{position.identity_status === "resolved" ? "Identity Resolved" : "Manual Ticker"}</Badge></div><p className="mt-1 truncate text-xs text-muted-foreground">{position.company_name || "No canonical company match in the local identity directory"}</p></div><div className="flex gap-1"><Button type="button" size="icon" variant="ghost" aria-label={`Edit ${position.ticker} holding`} onClick={() => editPosition(position)}><Pencil /></Button><Button type="button" size="icon" variant="ghost" aria-label={`Delete ${position.ticker} holding`} disabled={saving} onClick={() => void removePosition(position)}><Trash2 /></Button></div></div><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3"><div><dt className="text-xs text-muted-foreground">Shares</dt><dd className="mt-1 font-medium">{position.shares.toLocaleString()}</dd></div><div><dt className="text-xs text-muted-foreground">Cost Basis / Share</dt><dd className="mt-1 font-medium">{currency.format(position.cost_basis_per_share)}</dd></div><div><dt className="text-xs text-muted-foreground">Manual Market Value</dt><dd className="mt-1 font-medium">{position.manual_market_value === null ? "Not set" : currency.format(position.manual_market_value)}</dd></div></dl>{position.notes ? <p className="mt-3 overflow-wrap-anywhere text-xs leading-5 text-muted-foreground">{position.notes}</p> : null}</article>) : <div className="grid min-h-40 place-items-center rounded-lg border border-dashed px-6 text-center text-sm text-muted-foreground">No manual holdings yet. Add only positions that belong in your portfolio-level risk context.</div>}</div></TabsContent>
        </Tabs>}
      </ScrollArea>
    </SheetContent>
  </Sheet>
}
