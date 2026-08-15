import { ExternalLink, FileSearch } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { SourceEvidence } from "@/lib/types"

function sourceDate(value: string) {
  return new Date(value).toLocaleString()
}

export function SourceEvidenceDialog({
  evidence,
  label = "Inspect Evidence",
  title = "Source Evidence",
}: {
  evidence: SourceEvidence[]
  label?: string
  title?: string
}) {
  return <Dialog><DialogTrigger asChild><Button type="button" variant="outline" size="sm" disabled={!evidence.length}><FileSearch />{label}<Badge variant="secondary">{evidence.length}</Badge></Button></DialogTrigger><DialogContent className="sm:max-w-3xl"><DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>Exact source excerpts remain authoritative. Extracted labels and summaries are navigation aids only.</DialogDescription></DialogHeader><ScrollArea className="max-h-[70vh] pr-4"><div className="space-y-4">{evidence.map((item) => <article key={`${item.span.spanId}-${item.role}`} className="rounded-lg border bg-background/50 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap gap-2"><Badge>{item.role}</Badge><Badge variant="outline">{item.document.form || item.document.documentType}</Badge><Badge variant="secondary">Version {item.document.version}</Badge></div><h3 className="mt-3 font-semibold">{item.document.title || item.document.externalId}</h3><p className="mt-1 text-xs text-muted-foreground">Known {sourceDate(item.document.knownAt)} · retrieved {sourceDate(item.document.retrievedAt)}</p></div><Button asChild variant="outline" size="sm"><a href={item.document.sourceUrl} target="_blank" rel="noreferrer">Open Source<ExternalLink /></a></Button></div><div className="mt-4 rounded-md border-l-2 border-primary bg-muted/30 p-4 text-sm leading-6">“{item.span.exactText}”</div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground"><span>{item.span.section || "Section unavailable"}</span><span>{item.span.pageNumber ? `Page ${item.span.pageNumber}` : "Page unavailable"}</span><span>{item.span.extractionMethod}</span></div>{item.document.qualityWarnings.length ? <p className="mt-3 text-xs text-muted-foreground">{item.document.qualityWarnings.join(" ")}</p> : null}</article>)}</div></ScrollArea></DialogContent></Dialog>
}
