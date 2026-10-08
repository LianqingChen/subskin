<script setup lang="ts">
import { reportTime } from '@/utils/report-time'
import { useSkinReportList } from '@/composables/useSkinReportList'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
const { router, authStore, reports, loading, previews, typeFilter, isLoggedIn, filteredReports, typeTabs, previewBusy, previewDone, handleQuick, trendStyle, typeLabel, fmtDate } = useSkinReportList()
</script>

<template>
  <div class="srl-page">
    <header class="srl-header">
      <div class="srl-header__inner">
        <button class="srl-back" @click="router.push('/community')">
          <i class="ri-arrow-left-s-line"></i>
        </button>
        <h1 class="srl-header__title">白斑变化报告</h1>
        <button class="srl-new" @click="router.push({ name: 'skin-report-new' })">
          <i class="ri-add-line"></i>
        </button>
      </div>
    </header>

    <main class="srl-main">
      <LoadingSpinner v-if="loading" message="加载中..." />

      <EmptyState
        v-else-if="!isLoggedIn"
        icon="ri-lock-line"
        title="登录后查看你的白斑报告"
        description="白斑变化报告属于个人健康数据，需要登录后访问"
        action-label="登录 / 注册"
        @action="authStore.showLoginModal = true"
      />

      <template v-else>
        <!-- 周报/月报快捷生成 -->
        <div v-if="previews.length" class="srl-quick">
          <button
            v-for="p in previews"
            :key="p.label"
            class="srl-quick__card"
            :class="{ 'srl-quick__card--off': !p.can_generate && !previewDone(p) }"
            @click="p.can_generate || previewDone(p) ? handleQuick(p) : router.push({ name: 'skin-report-new' })"
          >
            <i
              class="srl-quick__icon"
              :class="p.period_type === 'weekly' ? 'ri-calendar-check-line' : 'ri-calendar-todo-line'"
            ></i>
            <div class="srl-quick__body">
              <div class="srl-quick__label">{{ p.label }}</div>
              <div class="srl-quick__meta">
                <template v-if="previewBusy(p)">
                  <i class="ri-loader-4-line ri-spin"></i> AI 分析中…
                </template>
                <template v-else-if="previewDone(p)">已生成 · 点击查看</template>
                <template v-else-if="p.can_generate">
                  {{ p.site_count }}个部位 {{ p.photo_count }}张照片可分析
                </template>
                <template v-else>本周期待新的白斑照片</template>
              </div>
            </div>
            <i
              v-if="!previewBusy(p) && (p.can_generate || previewDone(p))"
              class="ri-arrow-right-s-line srl-quick__arrow"
            ></i>
          </button>
        </div>

        <!-- 类型筛选 -->
        <div v-if="reports.length" class="srl-tabs">
          <button
            v-for="t in typeTabs"
            :key="t.key"
            class="srl-tab"
            :class="{ 'srl-tab--active': typeFilter === t.key }"
            @click="typeFilter = t.key"
          >
            {{ t.label }}
          </button>
        </div>

        <EmptyState
          v-if="reports.length === 0"
          icon="ri-file-chart-2-line"
          title="还没有报告"
          description="上传白斑照片生成周报/月报，或选择日记照片生成对比报告"
          action-label="生成第一份报告"
          @action="router.push({ name: 'skin-report-new' })"
        />

        <EmptyState
          v-else-if="filteredReports.length === 0"
          icon="ri-file-chart-2-line"
          title="该类型暂无报告"
          description="切换筛选或生成新报告"
        />

        <button
          v-for="r in filteredReports"
          :key="r.id"
          class="srl-card"
          @click="router.push({ name: 'skin-report-view', params: { id: r.id } })"
        >
          <div class="srl-card__top">
            <div class="srl-card__title-wrap">
              <i
                class="srl-card__type"
                :class="r.report_type === 'weekly' ? 'ri-calendar-check-line' : r.report_type === 'monthly' ? 'ri-calendar-todo-line' : 'ri-file-chart-2-line'"
              ></i>
              <span v-if="r.has_vasi" class="srl-card__vasi-tag"><i class="ri-microscope-line"></i> 深度评估</span>
              <span class="srl-card__title">{{ r.headline || r.title }}</span>
            </div>
            <span v-if="r.trend" class="srl-card__trend" :class="trendStyle(r.trend).cls">
              <i :class="trendStyle(r.trend).icon"></i> {{ r.trend }}
            </span>
          </div>
          <div class="srl-card__meta">
            <span><i class="ri-file-list-3-line"></i> {{ typeLabel(r.report_type) }}</span>
            <span v-if="r.sites_summary"><i class="ri-map-pin-line"></i> {{ r.sites_summary.total }}个部位</span>
            <span v-else><i class="ri-map-pin-line"></i> {{ r.body_site_label }}</span>
            <span><i class="ri-calendar-line"></i> {{ fmtDate(r.period_start) }} ~ {{ fmtDate(r.period_end) }}</span>
          </div>
          <div class="srl-card__footer">
            <time class="srl-card__date" :datetime="r.generated_at || r.created_at">{{ reportTime(r) }}</time>
            <span class="srl-card__share" v-if="r.is_public">
              <i class="ri-global-line"></i> 已分享
            </span>
          </div>
        </button>
      </template>
    </main>
  </div>
</template>

<style scoped src="@/components/report/SkinReportList.css"></style>
