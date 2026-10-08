<script setup lang="ts">
import { useSkinReportView } from '@/composables/useSkinReportView'
import { trendStyle, siteBadges, fmtDate, protectedUrl } from '@/utils/skin-report-presentation'
import { reportTime } from '@/utils/report-time'
import SkinReportPoster from '@/components/diary/SkinReportPoster.vue'
import HealthReportSections from '@/components/report/HealthReportSections.vue'
import ComparisonViews from '@/components/report/ComparisonViews.vue'
import PairDateSwitcher from '@/components/report/PairDateSwitcher.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import MicroAskCard from '@/components/contribution/MicroAskCard.vue'
import ContributionInviteCard from '@/components/contribution/ContributionInviteCard.vue'
const { report, loading, error, reportRef, chartRef, showPoster, exporting, sharing, isPeriodic, isSynthesis,
  isComparison, periodicSites, narrativeSections, coverUrl, chips, changeSummary, exportPdf, requestShare,
  shareToCommunity, copyLink, confirmDeleteVisible, handleDelete, onConfirmDelete, confirmShareVisible, router,
  frames, beforeIdx, afterIdx, activeAlign, activeMetrics, activeBeforeUrl, activeAfterUrl,
  activeBeforeDate, activeAfterDate, pairLoading } = useSkinReportView()
</script>

<template>
  <div class="report-page">
  <ConfirmDialog :visible="confirmShareVisible" title="确认分享到社区？" message="将在发现页创建公开帖子，包含本报告的标题、叙述摘要与报告链接。原始照片与分析明细不会公开。发布后可在社区删除该帖。" confirm-text="确认分享" @confirm="shareToCommunity" @cancel="confirmShareVisible = false" />
  <ConfirmDialog
    :visible="confirmDeleteVisible"
    title="删除确认"
    message="确定删除这份报告吗？删除后不可恢复。"
    confirm-text="删除"
    @confirm="onConfirmDelete"
    @cancel="confirmDeleteVisible = false"
  />

    <!-- Header -->
    <header class="report-header">
      <div class="report-header__inner">
        <button class="report-back" @click="router.back()">
          <i class="ri-arrow-left-s-line"></i>
        </button>
        <h1 class="report-header__title">白斑变化报告</h1>
        <button class="report-back" @click="handleDelete">
          <i class="ri-delete-bin-line"></i>
        </button>
      </div>
    </header>

    <main class="report-main">
      <div v-if="loading" class="report-loading">
        <i class="ri-loader-4-line report-spin"></i>
        <p>报告加载中...</p>
      </div>

      <div v-else-if="error" class="report-error">
        <i class="ri-file-damage-line"></i>
        <p>{{ error }}</p>
      </div>

      <template v-else-if="report">
        <!-- 后台生成中 -->
        <div v-if="report.status === 'generating'" class="report-loading">
          <i class="ri-loader-4-line report-spin"></i>
          <p>AI 正在分析你的白斑照片（约 1-2 分钟）…</p>
          <p class="report-loading__sub">页面会自动刷新，也可以稍后回来查看</p>
        </div>

        <div v-else-if="report.status === 'failed'" class="report-error">
          <i class="ri-file-damage-line"></i>
          <p>{{ report.error_message || '报告生成失败，请稍后重试' }}</p>
        </div>

        <!-- 报告文档区（固定浅色，确保 PDF 可读） -->
        <div v-else ref="reportRef" class="report-doc">
          <!-- 封面（对比报告：分层标题，简短有层次） -->
          <div class="report-cover">
            <div class="report-cover__brand">
              <i class="ri-leaf-line"></i>
              <span>SubSkin</span>
            </div>
            <template v-if="isComparison">
              <span class="report-cover__badge">
                <i class="ri-git-compare-line"></i> 对比报告
              </span>
              <h2 class="report-cover__headline">{{ report.body_site_label }}白斑变化报告</h2>
              <PairDateSwitcher v-if="frames.length > 2" :frames="frames" v-model:before-index="beforeIdx" v-model:after-index="afterIdx" :disabled="pairLoading" />
              <p v-else class="report-cover__meta" aria-label="对比照片日期">前：{{ fmtDate(activeBeforeDate || report.period_start) }} · 后：{{ fmtDate(activeAfterDate || report.period_end) }}</p>
              <div v-if="chips.length" class="report-cover__chips">
                <span v-for="(c, i) in chips" :key="i" class="rc-chip" :class="c.cls">
                  <i :class="c.icon"></i> {{ c.text }}
                </span>
              </div>
            </template>
            <template v-else>
              <h2 v-if="(isPeriodic || isSynthesis) && report.metrics?.headline" class="report-cover__headline">
                {{ report.metrics.headline }}
              </h2>
              <h2 v-else class="report-cover__headline">{{ report.title }}</h2>
              <div class="report-cover__meta-row">
                <p class="report-cover__meta">
                  {{ isSynthesis ? '历史报告对比' : '多部位汇总' }} ·
                  {{ fmtDate(report.period_start) }} ~ {{ fmtDate(report.period_end) }}
                </p>
                <div
                  v-if="report.metrics"
                  class="report-cover__trend"
                  :class="trendStyle(report.metrics.trend).bg"
                >
                  <i :class="trendStyle(report.metrics.trend).icon"></i>
                  <span>{{ trendStyle(report.metrics.trend).label }}</span>
                </div>
              </div>
            </template>
            <p class="report-cover__meta"><time :datetime="report.generated_at || report.created_at">{{ reportTime(report) }}</time></p>
          </div>

          <!-- 封面拼图（周报/月报） -->
          <img v-if="isPeriodic && coverUrl" :src="coverUrl" alt="白斑前后对比拼图" class="report-coverimg" />

          <!-- 前后对比（对比报告核心，置顶）：日期可切换 + 热力图 + 变化要点 -->
          <div v-if="isComparison && activeBeforeUrl && activeAfterUrl" class="report-section report-compare">
            <h3 class="report-section__title"><i class="ri-git-compare-line"></i> 前后对比</h3>

            <div class="report-compare__stage">
              <div v-if="pairLoading" class="report-compare__loading">
                <i class="ri-loader-4-line report-spin"></i>
                <span>AI 正在对比这两张照片…</span>
              </div>
              <ComparisonViews
                :before-url="activeBeforeUrl"
                :after-url="activeAfterUrl"
                :align="activeAlign"
                :metrics="activeMetrics"
                :before-label="activeBeforeDate"
                :after-label="activeAfterDate"
              />
            </div>
            <p v-if="frames.length > 2" class="ps-note">
              <i class="ri-information-line"></i>
              默认对比最早与最晚两张，点击标题栏日期可切换查看任意两次记录的对比
            </p>
          </div>

          <!-- 历史报告对比：来源报告 -->
          <div v-if="isSynthesis && report.metrics?.sources?.length" class="report-section">
            <h3 class="report-section__title"><i class="ri-file-list-3-line"></i> 来源报告</h3>
            <div class="src-list">
              <div v-for="s in report.metrics.sources" :key="s.report_id" class="src-item">
                <img
                  v-if="protectedUrl(s.cover_composite_url)"
                  :src="protectedUrl(s.cover_composite_url)"
                  alt="来源报告封面"
                  loading="lazy"
                />
                <i v-else class="ri-file-chart-line src-item__ph"></i>
                <div class="src-item__body">
                  <span class="src-item__title">{{ s.headline || s.title }}</span>
                  <span class="src-item__meta">{{ s.period }}</span>
                </div>
                <span v-if="s.trend" class="src-item__trend" :class="trendStyle(s.trend).bg">
                  <i :class="trendStyle(s.trend).icon"></i> {{ s.trend }}
                </span>
              </div>
            </div>
          </div>

          <!-- 周报/月报：部位总览 -->
          <div v-if="isPeriodic && report.metrics?.sites_summary" class="report-section">
            <h3 class="report-section__title"><i class="ri-body-scan-line"></i> 部位总览</h3>
            <div class="ps-overview">
              <div class="ps-overview__item ps-overview__item--good">
                <i class="ri-arrow-down-line"></i>
                <span>{{ report.metrics.sites_summary.improving }}</span>
                <em>好转</em>
              </div>
              <div class="ps-overview__item ps-overview__item--flat">
                <i class="ri-subtract-line"></i>
                <span>{{ report.metrics.sites_summary.stable }}</span>
                <em>稳定</em>
              </div>
              <div class="ps-overview__item ps-overview__item--bad">
                <i class="ri-arrow-up-line"></i>
                <span>{{ report.metrics.sites_summary.worsening }}</span>
                <em>需关注</em>
              </div>
              <div class="ps-overview__item">
                <i class="ri-camera-line"></i>
                <span>{{ report.metrics.period_days }}</span>
                <em>天周期</em>
              </div>
            </div>
            <div v-if="report.metrics.melanin_sites?.length" class="ps-melanin">
              <i class="ri-sparkling-line"></i>
              复色进行中：{{ report.metrics.melanin_sites.join('、') }}
            </div>
          </div>

          <!-- 周报/月报：分部位对比卡片 -->
          <div v-for="s in periodicSites" :key="s.body_site" class="report-section">
            <div class="ps-site-head">
              <h3 class="report-section__title ps-site-head__title">
                <i class="ri-focus-3-line"></i> {{ s.body_site_label }}
              </h3>
              <span class="ps-site-head__trend" :class="trendStyle(s.trend).bg">
                <i :class="trendStyle(s.trend).icon"></i> {{ s.trend }}
              </span>
            </div>
            <div v-if="siteBadges(s).length" class="ps-badges">
              <span v-for="(b, bi) in siteBadges(s)" :key="bi" class="ps-badge" :class="b.cls">
                <i :class="b.icon"></i> {{ b.text }}
              </span>
            </div>
            <div v-if="s.first_image_url && s.last_image_url" class="ps-split">
              <figure class="ps-split__item">
                <img
                  :src="protectedUrl(s.first_image_url)"
                  :alt="`${s.body_site_label} 之前`"
                  loading="lazy"
                />
                <figcaption>之前 · {{ fmtDate(s.first?.date ?? null) }}</figcaption>
              </figure>
              <figure class="ps-split__item">
                <img
                  :src="protectedUrl(s.last_image_url)"
                  :alt="`${s.body_site_label} 之后`"
                  loading="lazy"
                />
                <figcaption>之后 · {{ fmtDate(s.last?.date ?? null) }}</figcaption>
              </figure>
            </div>
            <p v-if="s.pair_metrics?.summary" class="ps-summary">{{ s.pair_metrics.summary }}</p>
            <p v-if="s.pair_metrics?.capture_note" class="ps-note">
              <i class="ri-information-line"></i> {{ s.pair_metrics.capture_note }}
            </p>
            <p v-if="s.pair_metrics?.low_confidence" class="ps-note ps-note--warn">
              <i class="ri-error-warning-line"></i>
              本次对比置信度较低（拍摄条件差异），建议同角度、同光线下拍摄以提升精度
            </p>
          </div>

          <!-- 综合健康报告：心情/体检/问答/概览 -->
          <HealthReportSections v-if="isPeriodic" :metrics="report.metrics" />

          <!-- VASI 趋势（客观数值曲线） -->
          <div v-if="report.metrics?.has_vasi" class="report-section">
            <h3 class="report-section__title"><i class="ri-line-chart-line"></i> VASI 趋势</h3>
            <div ref="chartRef" class="report-chart"></div>
          </div>

          <!-- 变化摘要（对比报告：客观事实，每条一句话，不做解读） -->
          <div v-if="isComparison && changeSummary.length" class="report-section">
            <h3 class="report-section__title"><i class="ri-file-list-3-line"></i> 变化摘要</h3>
            <ul class="report-facts">
              <li v-for="(line, i) in changeSummary" :key="i">
                <i class="ri-checkbox-circle-line"></i>
                <span>{{ line }}</span>
              </li>
            </ul>
          </div>

          <!-- AI 分析 / 洞察 / 建议：仅周报月报与历史报告对比保留（对比报告不再生成长文） -->
          <template v-if="!isComparison">
            <div v-if="narrativeSections.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-sparkling-2-line"></i> AI 分析</h3>
              <div v-for="(sec, si) in narrativeSections" :key="si" class="report-narrative__section">
                <h4 class="report-narrative__title">{{ sec.title }}</h4>
                <p class="report-narrative">{{ sec.body }}</p>
              </div>
            </div>
            <div v-else-if="report.narrative" class="report-section">
              <h3 class="report-section__title"><i class="ri-sparkling-2-line"></i> AI 分析</h3>
              <p class="report-narrative">{{ report.narrative }}</p>
            </div>

            <div v-if="report.insights?.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-lightbulb-line"></i> 关键洞察</h3>
              <ul class="report-list">
                <li v-for="(ins, i) in report.insights" :key="'ins-' + i">
                  <i class="ri-checkbox-circle-line"></i>
                  <span>{{ ins }}</span>
                </li>
              </ul>
            </div>

            <div v-if="report.recommendations?.length" class="report-section">
              <h3 class="report-section__title"><i class="ri-thumb-up-line"></i> 建议</h3>
              <ul class="report-list report-list--rec">
                <li v-for="(rec, i) in report.recommendations" :key="'rec-' + i">
                  <i class="ri-arrow-right-s-line"></i>
                  <span>{{ rec }}</span>
                </li>
              </ul>
            </div>
          </template>

          <!-- 免责声明 -->
          <div class="report-disclaimer">
            <i class="ri-error-warning-line"></i>
            <span v-if="isComparison">本报告为照片的客观比对结果，仅供参考，不构成医疗建议；如有疑问请咨询专业医生。</span>
            <span v-else>本报告由 AI 基于你的记录生成，仅供参考，不构成医疗诊断建议。如有疑问请咨询专业医生。</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div
          v-if="report.status === 'completed'"
          class="report-actions"
        >
          <button class="r-action" :disabled="exporting" @click="exportPdf">
            <i :class="exporting ? 'ri-loader-4-line report-spin' : 'ri-file-download-line'"></i>
            <span>PDF</span>
          </button>
          <button class="r-action" @click="showPoster = true">
            <i class="ri-image-2-line"></i>
            <span>海报</span>
          </button>
          <button class="r-action r-action--primary" :disabled="sharing" @click="requestShare">
            <i :class="sharing ? 'ri-loader-4-line report-spin' : 'ri-team-line'"></i>
            <span>{{ report.is_public ? '已分享' : '分享' }}</span>
          </button>
          <button class="r-action" @click="copyLink">
            <i class="ri-link"></i>
            <span>链接</span>
          </button>
        </div>

        <!-- 价值时刻：看完对比后，一次一个小问题；满意时再邀请（均可忽略） -->
        <div v-if="report.status === 'completed' && isComparison" class="mt-4 space-y-4">
          <MicroAskCard trigger="compare_viewed" />
          <ContributionInviteCard />
        </div>
      </template>
    </main>

    <!-- 海报弹层 -->
    <SkinReportPoster :visible="showPoster" :report="report" @close="showPoster = false" />
  </div>
</template>

<style scoped src="@/components/report/SkinReportView.css"></style>
