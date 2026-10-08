import { ref, onMounted, onBeforeUnmount, type Ref } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { SkinReport, TrendChartWithSeries } from '@/api/skin_report'
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])
export function useSkinReportChart(report: Ref<SkinReport | null>) {
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
function initChart() {
  if (!chartRef.value || !report.value?.trend_chart) return
  const tc = report.value.trend_chart

  // 周报/月报：多序列（每部位一条 VASI 曲线）
  if ('series' in tc && Array.isArray((tc as TrendChartWithSeries).series)) {
    const usable = (tc as TrendChartWithSeries).series.filter(
      (s) => s.vasi_scores.some((v) => v != null),
    )
    if (!usable.length) return
    chartInstance?.dispose()
    chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption({
      grid: { left: 44, right: 18, top: 38, bottom: 38 },
      tooltip: { trigger: 'axis' },
      legend: {
        top: 0,
        textStyle: { color: '#64748b', fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
      },
      xAxis: {
        type: 'category',
        data: [...new Set(usable.flatMap((s) => s.dates.map((d) => d.slice(5))))],
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: 'VASI',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      series: usable.map((s, idx) => ({
        name: s.body_site_label,
        type: 'line' as const,
        data: s.dates.map((d, i) => [d.slice(5), s.vasi_scores[i]]),
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { width: 3 },
        itemStyle: {},
        color: ['#0d9488', '#f59e0b', '#6366f1', '#ec4899'][idx % 4],
      })),
    })
    return
  }

  // 对比报告：单序列（旧格式）
  if (!('vasi_scores' in tc) || !tc.vasi_scores.some((v) => v != null)) return
  chartInstance?.dispose()
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption({
    grid: { left: 44, right: 18, top: 24, bottom: 38 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: tc.dates.map((d) => d.slice(5)),
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'VASI',
      nameTextStyle: { color: '#94a3b8', fontSize: 11 },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        name: 'VASI',
        type: 'line',
        data: tc.vasi_scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 3, color: '#0d9488' },
        itemStyle: { color: '#0d9488' },
        areaStyle: { color: 'rgba(13,148,136,0.12)' },
      },
    ],
  })
}

function handleResize() {
  chartInstance?.resize()
}


onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); chartInstance?.dispose() })
return { chartRef, initChart }
}
