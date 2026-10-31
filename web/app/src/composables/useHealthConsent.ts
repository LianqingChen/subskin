import { ref } from 'vue'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

export const HEALTH_CONSENT_DECLINED_MESSAGE = '未同意健康数据授权，本次未上传'

export class HealthConsentDeclined extends Error {
  constructor() {
    super(HEALTH_CONSENT_DECLINED_MESSAGE)
    this.name = 'HealthConsentDeclined'
  }
}

/** Resolver of the open dialog; non-null while HealthConsentDialog is shown. */
export const healthConsentPending = ref<((agreed: boolean) => void) | null>(null)

let grantedForUserId: number | null = null
let inFlight: Promise<void> | null = null

export function resolveHealthConsent(agreed: boolean): void {
  const resolve = healthConsentPending.value
  healthConsentPending.value = null
  resolve?.(agreed)
}

export function forgetHealthConsent(): void {
  grantedForUserId = null
}

async function recordConsent(source: string): Promise<void> {
  const { data: versions } = await apiClient.get<{ health_data_version?: string }>('/consent/versions')
  await apiClient.post('/consent/record', {
    consent_type: 'health_data',
    version: versions?.health_data_version || '1.0',
    platform: 'web',
    source,
  })
}

async function check(source: string): Promise<void> {
  const auth = useAuthStore()
  const userId = auth.user?.id ?? null
  if (!auth.isLoggedIn || userId === null) return
  if (grantedForUserId === userId) return

  try {
    const { data } = await apiClient.get<{ health_data?: unknown }>('/consent/status')
    if (data?.health_data) {
      grantedForUserId = userId
      return
    }
  } catch {
    // Status unavailable: don't block the upload; the server enforces consent when required.
    return
  }

  const agreed = await new Promise<boolean>((resolve) => { healthConsentPending.value = resolve })
  if (!agreed) throw new HealthConsentDeclined()
  await recordConsent(source)
  grantedForUserId = userId
}

/**
 * PIPL: health photos and reports are sensitive personal information and need a separate,
 * explicit consent before we store or process them. Throws HealthConsentDeclined on refusal.
 */
export function ensureHealthConsent(source: string): Promise<void> {
  if (!inFlight) inFlight = check(source).finally(() => { inFlight = null })
  return inFlight
}
