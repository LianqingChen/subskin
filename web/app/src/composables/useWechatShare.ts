import wx from 'weixin-js-sdk'
import { ref } from 'vue'

const isWechat = /MicroMessenger/i.test(navigator.userAgent)
const isReady = ref(false)

const DEFAULT_SHARE = {
    title: 'SubSkin - 白癜风病友的AI记录和分享社区',
    desc: '白癜风病友的AI记录和分享社区。',
  link: window.location.href.split('#')[0],
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
        'onMenuShareAppMessage',
        'onMenuShareTimeline',
      ],
    })

    wx.ready(() => {
      isReady.value = true
      setShareData({ ...DEFAULT_SHARE, link: window.location.href.split('#')[0] })
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

  const legacyAppMessage = {
    title: shareData.title,
    desc: shareData.desc,
    link: shareData.link,
    imgUrl: shareData.imgUrl,
    success() {},
    cancel() {},
  }
  wx.updateAppMessageShareData?.({ ...legacyAppMessage, success() {} })
  wx.updateTimelineShareData?.({
    title: shareData.title,
    link: shareData.link,
    imgUrl: shareData.imgUrl,
    success() {},
    cancel() {},
  })
  // Older WeChat WebView versions do not expose the update* APIs.
  wx.onMenuShareAppMessage?.(legacyAppMessage)
  wx.onMenuShareTimeline?.({
    title: shareData.title,
    link: shareData.link,
    imgUrl: shareData.imgUrl,
    success() {},
    cancel() {},
  })
}

export function useWechatShare() {
  return { isWechat, isReady, initWxConfig, setShareData }
}
