import apiClient from './client'
import type { ContributionDistribution, ContributionEvents, ContributionOverview, ContributionPersonalVisuals, ContributionTimeline, MyContributions } from '@/types/contribution'

export async function getContributionOverview(): Promise<ContributionOverview> {
  return (await apiClient.get('/contributions/overview')).data
}
export async function getContributionDistribution(): Promise<ContributionDistribution> {
  return (await apiClient.get('/contributions/distribution')).data
}
export async function getMyContributions(): Promise<MyContributions> {
  return (await apiClient.get('/contributions/me')).data
}
export async function syncContributionCredits(): Promise<void> {
  await apiClient.post('/contributions/me/sync')
}
export async function getContributionEvents(offset = 0): Promise<ContributionEvents> {
  return (await apiClient.get('/contributions/me/events', { params: { offset, limit: 5 } })).data
}
export async function getContributionTimeline(): Promise<ContributionTimeline> {
  return (await apiClient.get('/contributions/timeline')).data
}
export async function getPersonalContributionVisuals(): Promise<ContributionPersonalVisuals> {
  return (await apiClient.get('/contributions/me/visuals')).data
}
