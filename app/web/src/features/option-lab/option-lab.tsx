import { useCallback, useEffect, useState } from "react"
import { AlertCircle, Check, Circle, Database, FlaskConical } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { LifecycleWorkspace } from "@/features/option-lab/lifecycle-workspace"
import { OptionContextBar } from "@/features/option-lab/option-context-bar"
import {
  applyContractToLeg,
  createOptionDraft,
  FALLBACK_OPTION_TEMPLATES,
  replaceOptionTemplate,
  validateOptionDraft,
} from "@/features/option-lab/option-presets"
import { PositionBuilder } from "@/features/option-lab/position-builder"
import { ScenarioWorkspace } from "@/features/option-lab/scenario-workspace"
import {
  ApiError,
  applyOptionLifecycleEvent,
  createOptionPosition,
  loadChartData,
  loadOptionChain,
  loadOptionPosition,
  loadOptionPositions,
  loadOptionSimulationRun,
  loadOptionSimulationRuns,
  loadOptionTemplates,
  simulateOptionPosition,
} from "@/lib/api"
import type {
  OptionChainContract,
  OptionChainResponse,
  OptionLifecycleEvent,
  OptionPositionCreate,
  OptionPositionResponse,
  OptionPositionState,
  OptionPositionTemplate,
  OptionSimulationResult,
  OptionSimulationRunSummary,
} from "@/lib/types"
import { cn } from "@/lib/utils"

function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "The Option Lab request failed unexpectedly."
}

function OptionJourney({ simulation, ledger }: { simulation: OptionSimulationResult | null; ledger: OptionPositionResponse | null }) {
  const currentStage = ledger ? 3 : simulation ? 2 : 1
  const stages = [
    { number: 1, title: "Build", note: "Position and contracts" },
    { number: 2, title: "Explore", note: "Payoff and exposure" },
    { number: 3, title: "Journal", note: "Lifecycle decisions" },
  ]
  return <ol aria-label="Option Lab progress" className="grid overflow-hidden rounded-lg border sm:grid-cols-3">{stages.map((stage) => { const complete = stage.number < currentStage; const active = stage.number === currentStage; return <li key={stage.number} aria-current={active ? "step" : undefined} className={cn("flex items-center gap-3 border-b p-3 last:border-0 sm:border-b-0 sm:border-r sm:last:border-r-0", active && "bg-primary/8", complete && "bg-muted/35")}><span className={cn("grid size-7 shrink-0 place-items-center rounded-full border font-mono text-xs text-muted-foreground", active && "border-primary bg-primary text-primary-foreground", complete && "border-primary/50 text-primary")}>{complete ? <Check className="size-3.5" /> : active ? stage.number : <Circle className="size-3" />}</span><span><strong className={cn("block text-sm", active && "text-primary")}>{stage.title}</strong><small className="text-[10px] text-muted-foreground">{stage.note}</small></span></li> })}</ol>
}

export function OptionLab() {
  const [templates, setTemplates] = useState<OptionPositionTemplate[]>(FALLBACK_OPTION_TEMPLATES)
  const [templateError, setTemplateError] = useState("")
  const [draft, setDraft] = useState<OptionPositionCreate>(() => createOptionDraft(FALLBACK_OPTION_TEMPLATES[0]))
  const [chain, setChain] = useState<OptionChainResponse | null>(null)
  const [chainLoading, setChainLoading] = useState(false)
  const [chainError, setChainError] = useState("")
  const [simulation, setSimulation] = useState<OptionSimulationResult | null>(null)
  const [running, setRunning] = useState(false)
  const [ledger, setLedger] = useState<OptionPositionResponse | null>(null)
  const [creating, setCreating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [runs, setRuns] = useState<OptionSimulationRunSummary[]>([])
  const [runsLoading, setRunsLoading] = useState(false)
  const [positions, setPositions] = useState<OptionPositionState[]>([])
  const [positionsLoading, setPositionsLoading] = useState(false)

  const refreshRuns = useCallback(async () => {
    setRunsLoading(true)
    try {
      const payload = await loadOptionSimulationRuns()
      setRuns(payload.runs)
    } catch (error) {
      toast.error("Saved option runs are unavailable", { description: errorMessage(error) })
    } finally {
      setRunsLoading(false)
    }
  }, [])

  const refreshPositions = useCallback(async () => {
    setPositionsLoading(true)
    try {
      const payload = await loadOptionPositions()
      setPositions(payload.positions)
    } catch (error) {
      toast.error("Paper positions are unavailable", { description: errorMessage(error) })
    } finally {
      setPositionsLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void loadOptionTemplates().then((payload) => {
      if (!active || !payload.templates.length) return
      setTemplates(payload.templates)
      setTemplateError("")
    }).catch((error) => {
      if (!active) return
      setTemplateError(`${errorMessage(error)} Built-in position recipes remain available.`)
    })
    return () => { active = false }
  }, [])
  useEffect(() => { void refreshRuns() }, [refreshRuns])
  useEffect(() => { void refreshPositions() }, [refreshPositions])

  const changeDraft = (nextDraft: OptionPositionCreate) => {
    if (nextDraft.ticker !== draft.ticker) {
      setChain(null)
      setChainError("")
    }
    setDraft(nextDraft)
    setSimulation(null)
    setLedger(null)
  }

  const chooseTemplate = (template: OptionPositionTemplate) => {
    setDraft(replaceOptionTemplate(draft, template))
    setSimulation(null)
    setLedger(null)
  }

  const fetchChain = async (expiration?: string) => {
    if (!draft.ticker.trim()) return toast.error("Enter a US ticker before loading its current chain.")
    setChainLoading(true)
    try {
      const [nextChain, priceHistory] = await Promise.all([
        loadOptionChain(draft.ticker, expiration),
        chain ? Promise.resolve(null) : loadChartData(draft.ticker, "1mo", []),
      ])
      const latestPrice = priceHistory?.chart.at(-1)?.close
      setChain(nextChain)
      setChainError("")
      setSimulation(null)
      if (latestPrice) setDraft((current) => ({ ...current, underlying_price: latestPrice, share_cost_basis: ["covered_call", "conversion"].includes(current.position_kind) ? latestPrice : current.share_cost_basis }))
      toast.success(nextChain.expiration ? `${draft.ticker} ${nextChain.expiration} chain is ready.` : `No current ${draft.ticker} contracts were returned.`)
    } catch (error) {
      const message = errorMessage(error)
      setChainError(message)
      toast.error("Current chain unavailable", { description: message })
    } finally {
      setChainLoading(false)
    }
  }

  const selectContract = (legId: string, contract: OptionChainContract, expiration: string) => {
    setDraft((current) => applyContractToLeg(current, legId, contract, expiration))
    setSimulation(null)
    setLedger(null)
    toast.success(`Loaded ${contract.contract} into the selected leg.`)
  }

  const simulate = async () => {
    const validationError = validateOptionDraft(draft)
    if (validationError) return toast.error(validationError)
    setRunning(true)
    try {
      const result = await simulateOptionPosition({
        ...draft,
        run_name: draft.name,
        data_provenance: chain ? {
          source: chain.source || chain.dataStatus?.source || "Yahoo Finance",
          status: chain.dataStatus?.status || "Delayed",
          expiration: chain.expiration,
          observationTimestamp: chain.dataStatus?.observationTimestamp,
          knownAt: chain.dataStatus?.knownAt,
          qualityWarnings: chain.dataStatus?.qualityWarnings || [],
        } : { source: "Manual Inputs", status: "User Assumptions" },
      })
      setSimulation(result)
      setLedger(null)
      void refreshRuns()
      toast.success("Theoretical position evidence is ready.")
      window.setTimeout(() => document.getElementById("option-evidence")?.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }), 100)
    } catch (error) {
      toast.error("Option simulation failed", { description: errorMessage(error) })
    } finally {
      setRunning(false)
    }
  }

  const loadRun = async (runId: string) => {
    try {
      const run = await loadOptionSimulationRun(runId)
      const template = templates.find((item) => item.kind === run.positionKind)
      const name = run.runName || run.request.run_name || `${run.ticker} ${template?.name || run.positionKind.replaceAll("_", " ")}`
      setDraft({ ...run.request, name, research_run_id: null })
      setSimulation({ ...run.result, runId: run.runId, createdAt: run.createdAt, modelVersion: run.modelVersion })
      setLedger(null)
      setChain(null)
      setChainError("")
      toast.success(`Loaded immutable run ${run.runId.slice(0, 8)}.`)
    } catch (error) {
      toast.error("Option run could not be loaded", { description: errorMessage(error) })
    }
  }

  const loadPaperPosition = async (positionId: string) => {
    try {
      const response = await loadOptionPosition(positionId)
      const runId = response.position.research_run_id
      if (runId) {
        const run = await loadOptionSimulationRun(runId)
        const template = templates.find((item) => item.kind === run.positionKind)
        const name = run.runName || run.request.run_name || `${run.ticker} ${template?.name || run.positionKind.replaceAll("_", " ")}`
        setDraft({ ...run.request, name, research_run_id: runId })
        setSimulation({ ...run.result, runId: run.runId, createdAt: run.createdAt, modelVersion: run.modelVersion })
      } else {
        const position = response.position
        setDraft((current) => ({
          ...current,
          name: position.name,
          ticker: position.ticker,
          underlying_price: position.underlying_price,
          position_kind: position.position_kind,
          legs: position.legs,
          shares: Math.max(position.shares, 0),
          share_cost_basis: position.share_cost_basis > 0 ? position.share_cost_basis : null,
          research_run_id: null,
        }))
        setSimulation(null)
      }
      setLedger(response)
      setChain(null)
      setChainError("")
      toast.success(`Loaded paper ledger ${positionId.slice(0, 8)}.`)
    } catch (error) {
      toast.error("Paper position could not be loaded", { description: errorMessage(error) })
    }
  }

  const createPaperLedger = async () => {
    const validationError = validateOptionDraft(draft)
    if (validationError) {
      toast.error(validationError)
      return
    }
    if (draft.name.trim().length < 3) {
      toast.error("Name the paper position with at least three characters.")
      return
    }
    setCreating(true)
    try {
      const response = await createOptionPosition({ ...draft, research_run_id: simulation?.runId || null })
      setLedger(response)
      void refreshPositions()
      toast.success("Paper position saved locally. No order was sent.")
    } catch (error) {
      toast.error("Paper position could not be created", { description: errorMessage(error) })
    } finally {
      setCreating(false)
    }
  }

  const applyLifecycle = async (event: OptionLifecycleEvent) => {
    if (!ledger) return false
    setApplying(true)
    try {
      const response = await applyOptionLifecycleEvent(ledger.position.position_id, event)
      setLedger(response)
      void refreshPositions()
      toast.success("Lifecycle decision added to the local ledger.")
      return true
    } catch (error) {
      toast.error("Lifecycle event was rejected", { description: errorMessage(error) })
      return false
    } finally {
      setApplying(false)
    }
  }

  const sourceLabel = chain ? [chain.source || chain.dataStatus?.source || "Yahoo Finance", chain.dataStatus?.status || "Delayed", chain.expiration].filter(Boolean).join(" · ") : "Manual inputs · Load a current public chain when useful"
  return <>
    <OptionContextBar draft={draft} chainReady={Boolean(chain)} chainLoading={chainLoading} running={running} runs={runs} runsLoading={runsLoading} positions={positions} positionsLoading={positionsLoading} onChange={changeDraft} onLoadChain={() => void fetchChain()} onSimulate={() => void simulate()} onRefreshRuns={() => void refreshRuns()} onLoadRun={loadRun} onRefreshPositions={() => void refreshPositions()} onLoadPosition={loadPaperPosition} />
    <div className="space-y-5 p-3 sm:p-4 xl:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><div className="mb-2 flex items-center gap-2"><Badge variant="outline" className="border-primary/30 text-primary">Option Lifecycle Canvas</Badge><Badge variant="secondary">Paper Simulation</Badge></div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Explore the decisions between entry and expiry.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Construct a position, inspect model behavior, then journal hold, close, roll, exercise, expiry, or assignment events without connecting a brokerage account.</p></div><div className="flex items-center gap-2 font-mono text-[10px] text-muted-foreground"><Database className="size-4" />{sourceLabel}</div></div>
      <OptionJourney simulation={simulation} ledger={ledger} />
      {templateError && <Alert><AlertCircle /><AlertTitle>Using Built-In Position Recipes</AlertTitle><AlertDescription>{templateError}</AlertDescription></Alert>}
      {chainError && <Alert variant="destructive"><AlertCircle /><AlertTitle>Current Chain Unavailable</AlertTitle><AlertDescription>{chainError} Manual contract assumptions remain available.</AlertDescription></Alert>}
      <PositionBuilder draft={draft} templates={templates} chain={chain} chainLoading={chainLoading} chainError={chainError} onChange={changeDraft} onSelectTemplate={chooseTemplate} onLoadChain={(expiration) => void fetchChain(expiration)} onSelectContract={selectContract} />
      <ScenarioWorkspace simulation={simulation} loading={running} />
      <LifecycleWorkspace draft={draft} simulation={simulation} ledger={ledger} creating={creating} applying={applying} onDraftChange={setDraft} onCreate={createPaperLedger} onApply={applyLifecycle} />
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span><FlaskConical className="mr-1 inline size-3 text-primary" />Educational US equity-option research only. Outputs are theoretical and may use delayed public data.</span><span>No live brokerage execution.</span></div>
    </div>
  </>
}
