import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "SubSkin 百科全书",
  description: "白癜风百科全书 - 基于 AI 赋能的医学知识库",
  head: [
    ['link', { rel: 'icon', href: '/subskin_logo.png' }],
    ['meta', { name: 'theme-color', content: '#2563EB' }],
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1.0' }],
  ],
  base: '/encyclopedia/',
  themeConfig: {
    nav: [],
    sidebar: {
      '/encyclopedia/': [
        {
          text: '📖 百科导航',
          items: [
            { text: '百科首页', link: '/encyclopedia/' },
          ]
        },
        {
          text: '🔬 基础认知',
          collapsed: false,
          items: [
            { text: '什么是白癜风', link: '/encyclopedia/introduction/what-is-vitiligo' },
            { text: '病因与发病机制', link: '/encyclopedia/causes/' },
            { text: '流行病学', link: '/encyclopedia/epidemiology' },
          ]
        },
        {
          text: '🩺 诊断与检查',
          collapsed: false,
          items: [
            { text: '临床表现', link: '/encyclopedia/diagnosis/clinical-manifestations' },
            { text: '临床分型', link: '/encyclopedia/diagnosis/classification' },
            { text: '诊断方法', link: '/encyclopedia/diagnosis/diagnosis' },
          ]
        },
        {
          text: '💊 治疗方法',
          collapsed: false,
          items: [
            { text: '治疗原则', link: '/encyclopedia/treatment/principles' },
            { text: '药物治疗', link: '/encyclopedia/treatment/medications' },
            { text: '光疗', link: '/encyclopedia/treatment/phototherapy' },
            { text: '移植治疗', link: '/encyclopedia/treatment/transplantation' },
            { text: '中医中药', link: '/encyclopedia/treatment/chinese-medicine' },
          ]
        },
        {
          text: '🌿 生活管理',
          collapsed: false,
          items: [
            { text: '日常护理', link: '/encyclopedia/lifestyle/care' },
            { text: '饮食注意事项', link: '/encyclopedia/lifestyle/diet' },
            { text: '心理调节', link: '/encyclopedia/lifestyle/mental-health' },
          ]
        },
        {
          text: '🔬 最新研究',
          collapsed: false,
          items: [
            { text: '新药研发', link: '/encyclopedia/research/new-drugs' },
            { text: '临床试验', link: '/encyclopedia/research/clinical-trials' },
          ]
        },
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/LianqingChen/subskin' }
    ],
    logo: '/subskin_logo.png',
    siteTitle: 'SubSkin',
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: {
                buttonText: '搜索',
                buttonAriaLabel: '搜索'
              },
              modal: {
                noResultsText: '无法找到相关结果',
                resetButtonTitle: '清除查询条件',
                footer: {
                  selectText: '选择',
                  navigateText: '切换',
                  closeText: '关闭'
                }
              }
            }
          }
        }
      }
    },
    outline: {
      level: [2, 3],
      label: '页面导航'
    },
    docFooter: {
      prev: '上一页',
      next: '下一页'
    },
    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    externalLinkIcon: true,
    editLink: {
      pattern: 'https://github.com/LianqingChen/subskin/edit/main/web/vitepress/docs/:path',
      text: '在 GitHub 上编辑此页'
    },
    lastUpdated: {
      text: '更新于',
      formatOptions: {
        locale: 'zh-CN',
        dateStyle: 'full',
        timeStyle: 'medium'
      }
    },
    footer: {
      message: '基于最新医学研究，AI 辅助整理',
      copyright: '© 2024-2026 SubSkin · 内容仅供参考，不构成医疗建议'
    }
  },
  lang: 'zh-CN',
  cleanUrls: false,
  ignoreDeadLinks: true,
})