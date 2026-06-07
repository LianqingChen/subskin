import wx from 'weixin-js-sdk'
import { ref } from 'vue'

const isWechat = /MicroMessenger/i.test(navigator.userAgent)
const isReady = ref(false)

const DEFAULT_SHARE = {
    title: 'SubSkin更懂你',
    desc: 'SubSkin更懂你。AI赋能的白癜风知识库与社区平台。',
  link: window.location.origin,
  imgUrl: `${window.location.origin}/og-image.png`,
}

async function initWxConfig() {
  if (!isWechat) return
  try {
    const url = encodeURIComponent(window.location.href.split('#')[0])
    const res = await fetch(`/api/wechat/jssdk-config?url=${url}`)
    if (!res.ok) {
      console.warn('[wx] jssdk-config failed:', res.status)
      return
    }
    const config = await res.json()

    wx.config({
      debug: false,
      appId: config.appId,
      timestamp: config.timestamp,
      nonceStr: config.nonceStr,
      signature: config.signature,
      jsApiList: [
        'updateAppMessageShareData',
        'updateTimelineShareData',
      ],
    })

    wx.ready(() => {
      isReady.value = true
      setShareData(DEFAULT_SHARE)
    })

    wx.error((err: { errMsg: string }) => {
      console.warn('[wx] config error:', err.errMsg)
    })
  } catch (e) {
    console.warn('[wx] init failed:', e)
  }
}

export function setShareData(data: {
  title?: string
  desc?: string
  link?: string
  imgUrl?: string
}) {
  if (!isWechat || !isReady.value) return

  const shareData = {
    title: data.title || DEFAULT_SHARE.title,
    desc: data.desc || DEFAULT_SHARE.desc,
    link: data.link || DEFAULT_SHARE.link,
    imgUrl: data.imgUrl || DEFAULT_SHARE.imgUrl,
  }

  wx.updateAppMessageShareData({ ...shareData, success() {} })
  wx.updateTimelineShareData({
    title: shareData.title,
    link: shareData.link,
    imgUrl: shareData.imgUrl,
    success() {},
  })
}

export function useWechatShare() {
  return { isWechat, isReady, initWxConfig, setShareData }
}
