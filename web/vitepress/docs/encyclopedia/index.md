---
title: 白癜风百科全书
layout: page
---

<script setup>
const stats = [
  { number: '2000+', label: '权威医学文献' },
  { number: '5', label: '知识分类' },
  { number: '16', label: '专业文章' },
  { number: '100%', label: 'AI 辅助整理' },
]

const categories = [
  {
    icon: '🔬',
    title: '基础认知',
    desc: '了解白癜风的基本定义、发病原因和流行情况，掌握疾病全貌',
    pages: [
      { text: '什么是白癜风', link: '/encyclopedia/introduction/what-is-vitiligo.html' },
      { text: '病因与发病机制', link: '/encyclopedia/causes/' },
      { text: '流行病学', link: '/encyclopedia/epidemiology.html' },
    ]
  },
  {
    icon: '🩺',
    title: '诊断与检查',
    desc: '临床表现、分型标准和诊断方法，帮助早期识别与规范评估',
    pages: [
      { text: '临床表现', link: '/encyclopedia/diagnosis/clinical-manifestations.html' },
      { text: '临床分型', link: '/encyclopedia/diagnosis/classification.html' },
      { text: '诊断方法', link: '/encyclopedia/diagnosis/diagnosis.html' },
    ]
  },
  {
    icon: '💊',
    title: '治疗方法',
    desc: '药物、光疗、移植及中医等各类治疗手段全面解读',
    pages: [
      { text: '治疗原则', link: '/encyclopedia/treatment/principles.html' },
      { text: '药物治疗', link: '/encyclopedia/treatment/medications.html' },
      { text: '光疗', link: '/encyclopedia/treatment/phototherapy.html' },
      { text: '移植治疗', link: '/encyclopedia/treatment/transplantation.html' },
      { text: '中医中药', link: '/encyclopedia/treatment/chinese-medicine.html' },
    ]
  },
  {
    icon: '🌿',
    title: '生活管理',
    desc: '日常护理、饮食调理和心理调适，全方位改善生活质量',
    pages: [
      { text: '日常护理', link: '/encyclopedia/lifestyle/care.html' },
      { text: '饮食注意事项', link: '/encyclopedia/lifestyle/diet.html' },
      { text: '心理调节', link: '/encyclopedia/lifestyle/mental-health.html' },
    ]
  },
  {
    icon: '📊',
    title: '最新研究',
    desc: '前沿新药研发进展和临床试验动态，追踪最新治疗方向',
    pages: [
      { text: '新药研发', link: '/encyclopedia/research/new-drugs.html' },
      { text: '临床试验', link: '/encyclopedia/research/clinical-trials.html' },
    ]
  },
]

const quickLinks = [
  { icon: '❓', text: '常见问题', link: '/encyclopedia/faq/common-questions.html' },
  { icon: '🔬', text: '什么是白癜风', link: '/encyclopedia/introduction/what-is-vitiligo.html' },
  { icon: '💊', text: '药物治疗', link: '/encyclopedia/treatment/medications.html' },
  { icon: '☀️', text: '光疗指南', link: '/encyclopedia/treatment/phototherapy.html' },
  { icon: '🧠', text: '心理调节', link: '/encyclopedia/lifestyle/mental-health.html' },
  { icon: '🆕', text: '新药研发', link: '/encyclopedia/research/new-drugs.html' },
]
</script>

<div class="enc-hero">
  <div class="enc-hero-badge">📖 患者友好的医学科普</div>
  <h1 class="enc-hero-title">白癜风百科全书</h1>
  <p class="enc-hero-desc">基于 2000+ 篇权威医学文献，通过 AI 技术整理为患者友好的科普内容。从基础认知到前沿研究，帮助您全面了解白癜风。</p>
  <div class="enc-hero-actions">
    <a href="/wiki-content/encyclopedia/introduction/what-is-vitiligo.html" class="enc-hero-btn enc-hero-btn--primary">开始阅读 →</a>
    <a href="/wiki-content/encyclopedia/faq/common-questions.html" class="enc-hero-btn">常见问题</a>
  </div>
</div>

<div class="enc-stats">
  <div v-for="stat in stats" :key="stat.label" class="enc-stat-card">
    <div class="enc-stat-number">{{ stat.number }}</div>
    <div class="enc-stat-label">{{ stat.label }}</div>
  </div>
</div>

<div class="enc-callout enc-callout-warning">
  <div class="enc-callout-title">⚠️ 重要声明</div>
  <p>本百科所有内容基于权威医学文献整理，仅供参考学习使用，<strong>不构成任何医疗诊断或治疗建议</strong>。具体诊疗请务必咨询专业医师。</p>
</div>

<h2 class="enc-section-title">知识分类</h2>

<div class="enc-grid">
  <a v-for="cat in categories" :key="cat.title" :href="'/wiki-content' + cat.pages[0].link" class="enc-card">
    <div class="enc-card-icon">{{ cat.icon }}</div>
    <div class="enc-card-title">{{ cat.title }}</div>
    <div class="enc-card-desc">{{ cat.desc }}</div>
    <div class="enc-card-footer">
      <span class="enc-card-count">{{ cat.pages.length }} 篇文章</span>
      <span class="enc-card-arrow">查看详情 →</span>
    </div>
  </a>
</div>

<div class="enc-callout enc-callout-info">
  <div class="enc-callout-title">💡 使用提示</div>
  <p>左侧边栏可以快速导航到各个章节，每个页面都有详细目录。如需专业医疗建议，请咨询执业医师。</p>
</div>

<h2 class="enc-section-title">快速阅读</h2>

<div class="enc-quick-links">
  <a v-for="link in quickLinks" :key="link.text" :href="'/wiki-content' + link.link" class="enc-quick-link">
    <span class="enc-quick-link-icon">{{ link.icon }}</span>
    <span>{{ link.text }}</span>
  </a>
</div>