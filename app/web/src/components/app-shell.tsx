import type { ReactNode } from "react"
import { BarChart3, FlaskConical, Gauge, LineChart, Orbit } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const navigation = [
  { label: "Strategy Lab", icon: FlaskConical, active: true, href: "/" },
  { label: "Option Lab", icon: Orbit, href: "/legacy?panel=options" },
  { label: "Stock Observatory", icon: LineChart, href: "/legacy?panel=stock" },
  { label: "Market Pulse", icon: Gauge, href: "/legacy?panel=market" },
]

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_55%_-20%,rgba(182,245,89,0.07),transparent_35%),var(--background)]">
      <a href="#strategy-main" className="fixed left-3 top-3 z-50 -translate-y-20 rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-transform focus:translate-y-0">Skip To Research</a>
      <aside aria-label="Primary navigation" className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r bg-[#09120f]/95 p-5 backdrop-blur lg:flex lg:flex-col">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-9 place-items-center rounded-md border border-primary/40 bg-primary/10 text-primary"><BarChart3 className="size-5" /></div>
          <div><div className="font-semibold tracking-[0.16em]">GBB TERMINAL</div><div className="font-mono text-[9px] text-muted-foreground">RESEARCH WORKBENCH</div></div>
        </div>
        <nav aria-label="Research laboratories" className="mt-12 space-y-1">
          {navigation.map((item) => <a key={item.label} href={item.href} aria-current={item.active ? "page" : undefined} className={cn("flex items-center gap-3 rounded-md px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground", item.active && "bg-primary/10 text-primary")}><item.icon aria-hidden="true" className="size-4" /><span>{item.label}</span>{!item.active && <span className="ml-auto font-mono text-[8px]">LEGACY</span>}</a>)}
        </nav>
        <div className="mt-auto space-y-3 rounded-lg border bg-card/70 p-3">
          <div className="flex items-center gap-2"><span className="size-2 rounded-full bg-primary shadow-[0_0_10px_var(--primary)]" /><span className="font-mono text-[9px] text-primary">LOCAL · READY</span></div>
          <p className="m-0 text-xs leading-5 text-muted-foreground">Educational US equity and options research. No brokerage execution.</p>
          <Badge variant="outline" className="font-mono text-[9px]">v0.4.3 canvas</Badge>
        </div>
      </aside>
      <header className="border-b bg-background/95 px-3 py-3 lg:hidden">
        <div className="flex items-center justify-between px-1"><span className="font-semibold tracking-[0.15em]">GBB TERMINAL</span><Badge variant="outline">Strategy Lab</Badge></div>
        <nav aria-label="Mobile research laboratories" className="mt-3 flex gap-1 overflow-x-auto pb-1">
          {navigation.map((item) => <a key={item.label} href={item.href} aria-current={item.active ? "page" : undefined} className={cn("shrink-0 rounded-md px-3 py-2 text-xs text-muted-foreground", item.active ? "bg-primary/10 text-primary" : "bg-muted/40 hover:text-foreground")}><item.icon aria-hidden="true" className="mr-1.5 inline size-3" />{item.label}</a>)}
        </nav>
      </header>
      <main id="strategy-main" tabIndex={-1} className="min-h-screen lg:pl-60">{children}</main>
    </div>
  )
}
