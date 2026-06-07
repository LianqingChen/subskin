async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

function normalizePhone(phone: string): string {
  return phone
    .trim()
    .replace(/[\s\-()]/g, '')
    .replace(/^\+86/, '')
}

export async function hashPhone(phone: string): Promise<string> {
  const normalized = normalizePhone(phone)
  return sha256(normalized)
}

export interface ContactEntry {
  name: string
  phone: string
  hash: string
}

export async function hashContacts(
  contacts: Array<{ name?: string; phone: string }>,
): Promise<ContactEntry[]> {
  const results: ContactEntry[] = []
  for (const c of contacts) {
    const normalized = normalizePhone(c.phone)
    if (!normalized || normalized.length < 5) continue
    const hash = await hashPhone(c.phone)
    results.push({
      name: c.name || '',
      phone: normalized,
      hash,
    })
  }
  return results
}

/**
 * Read device contacts using the Contact Picker API.
 * IMPORTANT: Must be called from a user gesture (click/tap), otherwise
 * the browser will either reject or hang indefinitely.
 * Returns null if API is unavailable or user cancels.
 */
export async function readDeviceContacts(): Promise<
  Array<{ name: string; phone: string }> | null
> {
  if (!('contacts' in navigator) || !(navigator as any).contacts) {
    return null
  }

  try {
    const contactsApi = (navigator as any).contacts
    const props = await contactsApi.getProperties()
    if (!props.includes('tel')) return null

    // Add timeout: Contact Picker can hang if called without user gesture
    const selectPromise = contactsApi.select(['name', 'tel'], {
      multiple: true,
    })
    const timeoutPromise = new Promise<null>((resolve) =>
      setTimeout(() => resolve(null), 10000),
    )
    const contacts = await Promise.race([selectPromise, timeoutPromise])
    if (!contacts) return null

    const result: Array<{ name: string; phone: string }> = []
    for (const c of contacts) {
      const name = c.name?.[0] || ''
      const phones = c.tel || []
      for (const tel of phones) {
        if (tel.value) {
          result.push({ name, phone: tel.value })
        }
      }
    }
    return result
  } catch {
    return null
  }
}
