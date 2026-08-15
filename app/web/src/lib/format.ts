export function ordinal(value: number) {
  const rounded = Math.round(value)
  const absolute = Math.abs(rounded)
  const remainder100 = absolute % 100

  if (remainder100 >= 11 && remainder100 <= 13) return `${rounded}th`

  const suffix = absolute % 10 === 1 ? "st" : absolute % 10 === 2 ? "nd" : absolute % 10 === 3 ? "rd" : "th"
  return `${rounded}${suffix}`
}
