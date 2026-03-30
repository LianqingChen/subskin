import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "SubSkin",
  description: "白癜风百科全书 - 利用 AI 赋能，缩短医学前沿与普通患者之间的知识鸿沟",
  head: [
    ['link', { rel: 'icon', href: '/subskin_logo.png' }]
  ],
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '关于', link: '/community/about' },
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
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/yourusername/subskin' }
    ],
    logo: '/subskin_logo.png',
  },
  lang: 'zh-CN',
})
