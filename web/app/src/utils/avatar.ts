/**
 * Avatar initial fallback logic.
 * Masked usernames (e.g. 138****2222) start with a digit — showing it as an
 * avatar initial is meaningless and leaks data shape. Fall back to brand char.
 */
export function avatarInitial(name?: string | null): string {
  const c = (name || '').trim().charAt(0)
  if (!c || /[\d*#]/.test(c)) return '白'
  return c.toUpperCase()
}
