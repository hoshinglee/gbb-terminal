import type { ReactNode } from "react"
import { BarChart3, Building2, FlaskConical, Gauge, NotebookTabs, Orbit } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { PortfolioRiskSheet } from "@/features/portfolio/portfolio-risk-sheet"
import type { LabId } from "@/lib/navigation"
import { cn } from "@/lib/utils"

const navigation = [
  { id: "strategy", label: "Strategy Lab", icon: FlaskConical, href: "/" },
  { id: "options", label: "Option Lab", icon: Orbit, href: "/?lab=options" },
  { id: "market", label: "Market Pulse", icon: Gauge, href: "/?lab=market" },
  { id: "intelligence", label: "Company Intelligence", icon: Building2, href: "/?lab=intelligence" },
  { id: "decision", label: "Decision Center", icon: NotebookTabs, href: "/?lab=decision" },
] as const

const mainIds: Record<LabId, string> = {
  strategy: "strategy-main",
  options: "option-main",
  market: "market-main",
  intelligence: "intelligence-main",
  decision: "decision-main",
}

export function AppShell({ children, activeLab = "strategy" }: { children: ReactNode; activeLab?: LabId }) {
  const mainId = mainIds[activeLab]
  const labName = navigation.find((item) => item.id === activeLab)?.label || "Research"
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_55%_-20%,rgba(182,245,89,0.07),transparent_35%),var(--background)]">
      <a href={`#${mainId}`} className="fixed left-3 top-3 z-50 -translate-y-20 rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-transform focus:translate-y-0">Skip To Research</a>
      <aside aria-label="Primary navigation" className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r bg-[#09120f]/95 p-5 backdrop-blur lg:flex lg:flex-col">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-9 place-items-center rounded-md border border-primary/40 bg-primary/10 text-primary"><BarChart3 className="size-5" /></div>
          <div><div className="font-semibold tracking-[0.16em]">GBB TERMINAL</div><div className="font-mono text-[9px] text-muted-foreground">RESEARCH WORKBENCH</div></div>
        </div>
        <nav aria-label="Research laboratories" className="mt-12 space-y-1">
          {navigation.map((item) => { const active = item.id === activeLab; return <a key={item.label} href={item.href} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-3 rounded-md px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground", active && "bg-primary/10 text-primary")}><item.icon aria-hidden="true" className="size-4" /><span>{item.label}</span></a> })}
        </nav>
        <div className="mt-auto space-y-3 rounded-lg border bg-card/70 p-3">
          <div className="flex items-center gap-2"><span className="size-2 rounded-full bg-primary shadow-[0_0_10px_var(--primary)]" /><span className="font-mono text-[9px] text-primary">LOCAL · READY</span></div>
          <p className="m-0 text-xs leading-5 text-muted-foreground">Educational US equity and options research. No brokerage execution.</p>
          <PortfolioRiskSheet />
          <a href="/legacy" className="block text-[10px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Open Migration Fallback</a>
          <Badge variant="outline" className="font-mono text-[9px]">v0.11 decision context</Badge>
        </div>
      </aside>
      <header className="border-b bg-background/95 px-3 py-3 lg:hidden">
        <div className="flex items-center justify-between gap-3 px-1"><span className="font-semibold tracking-[0.15em]">GBB TERMINAL</span><div className="flex items-center gap-2"><Badge variant="outline">{labName}</Badge><PortfolioRiskSheet compact /></div></div>
        <nav aria-label="Mobile research laboratories" className="mt-3 flex gap-1 overflow-x-auto pb-1">
          {navigation.map((item) => { const active = item.id === activeLab; return <a key={item.label} href={item.href} aria-current={active ? "page" : undefined} className={cn("shrink-0 rounded-md px-3 py-2 text-xs text-muted-foreground", active ? "bg-primary/10 text-primary" : "bg-muted/40 hover:text-foreground")}><item.icon aria-hidden="true" className="mr-1.5 inline size-3" />{item.label}</a> })}
        </nav>
      </header>
      <main id={mainId} tabIndex={-1} className="min-h-screen lg:pl-60">{children}</main>
    </div>
  )
}
