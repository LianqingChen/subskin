import { isAxiosError } from 'axios'
export function assessmentError(error: unknown, fallback: string): string {
  if (isAxiosError<{ detail?: unknown }>(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail
  }
  return fallback
}
