import { lazy, Suspense } from "react"

import { AppShell } from "@/components/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"
import { labFromSearch, tickerFromSearch } from "@/lib/navigation"

const MarketPulse = lazy(() => import("@/features/market-pulse/market-pulse").then((module) => ({ default: module.MarketPulse })))
const OptionLab = lazy(() => import("@/features/option-lab/option-lab").then((module) => ({ default: module.OptionLab })))
const StockObservatory = lazy(() => import("@/features/stock-observatory/stock-observatory").then((module) => ({ default: module.StockObservatory })))
const StrategyLab = lazy(() => import("@/features/strategy-lab/strategy-lab").then((module) => ({ default: module.StrategyLab })))

export function App() {
  const activeLab = labFromSearch(window.location.search)
  const initialTicker = tickerFromSearch(window.location.search)
  const canvas = activeLab === "options"
    ? <OptionLab initialTicker={initialTicker} />
    : activeLab === "stock"
      ? <StockObservatory initialTicker={initialTicker} />
      : activeLab === "market"
        ? <MarketPulse />
        : <ResearchWorkspaceProvider initialTicker={initialTicker}><StrategyLab /></ResearchWorkspaceProvider>
  return <TooltipProvider><AppShell activeLab={activeLab}><Suspense fallback={<div className="grid min-h-screen place-items-center font-mono text-xs text-muted-foreground">Loading research canvas…</div>}>{canvas}</Suspense></AppShell><Toaster position="bottom-right" richColors /></TooltipProvider>
}
