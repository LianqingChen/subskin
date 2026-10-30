/** RGB 分割训练（/vasi/admin/rgb-training/*）的响应结构。 */
export interface Gate {
  passed: boolean
  reasons: string[]
  dice?: number | null
  skin_dice?: number | null
  baseline_dice?: number | null
  test_subjects?: number
}

export interface DatasetReport {
  dataset_id: string
  items: number
  subjects: number
  counts: Record<string, number>
  negatives?: number
  benchmark_items?: number
  expires_at?: string | null
  valid: boolean
  error: string | null
  skipped: unknown[]
}

export interface Run {
  run_id: string
  dataset_id: string
  epochs: number
  state: string
  error: string | null
  created_at: string
  epochs_run?: number
  gate: Gate
}

export interface Registry {
  enabled: boolean | null
  model_id: string | null
  dataset_review_id: string | null
  registered_at: string | null
  run_id: string | null
}

export interface TrainingStatus {
  rgb_labels: number
  admin_labeled: number
  gold: number
  gold_consented: number
  gold_consent_withdrawn: number
  subjects: number
  benchmark_gold: number
  gate: { min_test_images: number; min_test_subjects: number; min_dice: number; min_skin_dice: number }
  datasets: DatasetReport[]
  runs: Run[]
  registry: Registry
}
