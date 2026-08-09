export function chartKeyboardIndex(key: string, current: number | null, length: number): number | null {
  if (length <= 0) return null
  const last = length - 1
  const active = current ?? last
  if (key === "ArrowLeft") return Math.max(0, active - 1)
  if (key === "ArrowRight") return Math.min(last, active + 1)
  if (key === "Home") return 0
  if (key === "End") return last
  return null
}
