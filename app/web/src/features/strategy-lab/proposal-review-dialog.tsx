import { AlertTriangle, Bot, CheckCircle2 } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { LegacyProposal } from "@/lib/types"

interface ProposalReviewDialogProps {
  proposal: LegacyProposal | null
  open: boolean
  running: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function ProposalReviewDialog({ proposal, open, running, onOpenChange, onConfirm }: ProposalReviewDialogProps) {
  const risk = (proposal?.strategy.parameters?.risk || {}) as Record<string, number>
  return <Dialog open={open} onOpenChange={(next) => !running && onOpenChange(next)}><DialogContent className="sm:max-w-2xl"><DialogHeader><div className="flex items-center gap-2"><Badge variant="outline"><Bot />{proposal?.provider || "Translator"}</Badge>{proposal?.existingStrategy && <Badge variant="secondary">Existing Catalogue Match</Badge>}</div><DialogTitle className="pt-2">Review The Proposed Strategy</DialogTitle><DialogDescription>Natural language never becomes executable Python. Confirm the normalized declarative rule before research runs.</DialogDescription></DialogHeader>{proposal && <div className="space-y-4"><div className="rounded-lg border bg-muted/30 p-4"><p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Proposed Name</p><p className="mt-2 text-lg font-semibold">{proposal.strategy.name}</p><p className="mt-2 text-sm leading-6 text-muted-foreground">{proposal.normalizedInstruction || proposal.strategy.description}</p>{Object.keys(risk).length > 0 && <div className="mt-3 flex flex-wrap gap-2">{risk.trailing_stop_percent !== undefined && <Badge>Trailing Stop {risk.trailing_stop_percent}%</Badge>}{risk.stop_loss_percent !== undefined && <Badge variant="secondary">Stop Loss {risk.stop_loss_percent}%</Badge>}{risk.take_profit_percent !== undefined && <Badge variant="secondary">Take Profit {risk.take_profit_percent}%</Badge>}</div>}</div>{proposal.clarifications.length ? <Alert variant="destructive"><AlertTriangle /><AlertTitle>Clarification Applied</AlertTitle><AlertDescription>{proposal.clarifications.map((clarification) => <p key={clarification}>{clarification}</p>)}</AlertDescription></Alert> : <Alert className="border-primary/25 bg-primary/5"><CheckCircle2 /><AlertTitle>Instruction Is Sufficiently Specific</AlertTitle><AlertDescription>The translated rule passed schema and indicator validation. Review it once more before running.</AlertDescription></Alert>}<p className="text-xs leading-5 text-muted-foreground">The advanced export remains hidden from the common workflow. It can be downloaded later from catalogue tools when direct editing is intentionally supported.</p></div>}<DialogFooter><Button variant="outline" disabled={running} onClick={() => onOpenChange(false)}>Continue Editing</Button><Button disabled={!proposal || running} onClick={onConfirm}>{running ? "Running Research…" : proposal?.existingStrategy ? "Use Existing And Run" : "Confirm And Run"}</Button></DialogFooter></DialogContent></Dialog>
}
