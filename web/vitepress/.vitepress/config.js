import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "SubSkin",
  description: "白癜风百科全书 - 利用 AI 赋能，缩短医学前沿与普通患者之间的知识鸿沟",
  head: [
    ['link', { rel: 'icon', href: '/subskin_logo.png' }],
    ['meta', { name: 'theme-color', content: '#3eaf7c' }]
  ],
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '百科', link: '/encyclopedia/' },
      { text: '动态', link: '/news/' },
      { text: '社区', link: '/community/about' },
    ],
    sidebar: {
      '/community/': [
        {
          text: '关于项目',
          items: [
            { text: '关于 SubSkin', link: '/community/about' }
          ]
        }
      ],
      '/encyclopedia/': [
        {
          text: '基础认知',
          items: [
            { text: '概述', link: '/encyclopedia/' },
            { text: '什么是白癜风', link: '/encyclopedia/introduction/what-is-vitiligo' },
            { text: '病因与发病机制', link: '/encyclopedia/causes/' },
            { text: '流行病学', link: '/encyclopedia/epidemiology' }
          ]
        },
        {
          text: '诊断与检查',
          items: [
            { text: '临床表现', link: '/encyclopedia/diagnosis/clinical-manifestations' },
            { text: '临床分型', link: '/encyclopedia/diagnosis/classification' },
            { text: '诊断方法', link: '/encyclopedia/diagnosis/diagnosis' }
          ]
        },
        {
          text: '治疗方法',
          items: [
            { text: '治疗原则', link: '/encyclopedia/treatment/principles' },
            { text: '药物治疗', link: '/encyclopedia/treatment/medications' },
            { text: '光疗', link: '/encyclopedia/treatment/phototherapy' },
            { text: '移植治疗', link: '/encyclopedia/treatment/transplantation' },
            { text: '中医中药', link: '/encyclopedia/treatment/chinese-medicine' }
          ]
        },
        {
          text: '生活管理',
          items: [
            { text: '日常护理', link: '/encyclopedia/lifestyle/care' },
            { text: '饮食', link: '/encyclopedia/lifestyle/diet' },
            { text: '心理调节', link: '/encyclopedia/lifestyle/mental-health' }
          ]
        },
        {
          text: '最新研究',
          items: [
            { text: '新药研发', link: '/encyclopedia/research/new-drugs' },
            { text: '临床试验', link: '/encyclopedia/research/clinical-trials' }
          ]
        }
      ],
      '/news/': [
        {
          text: '最新动态',
          items: [
            { text: '每周更新列表', link: '/news/' },
            { text: '2026年第13周', link: '/news/2026/week-13' }
          ]
        }
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/yourusername/subskin' }
    ],
    logo: '/subskin_logo.png',
    search: {
      provider: 'local'
    },
    outline: {
      level: [2, 3]
    },
    docFooter: {
      prev: '上一页',
      next: '下一页'
    }
  },
  lang: 'zh-CN',
  cleanUrls: true,
  ignoreDeadLinks: true,
  lastUpdated: {
    text: '更新时间',
    formatOptions: {
      locale: 'zh-CN',
      dateStyle: 'full',
      timeStyle: 'medium'
    }
  }
})
