// pages/webview/webview.ts
Page({
  data: {
    url: '',
  },

  onLoad(options: any) {
    const url = decodeURIComponent(options.url || '')
    this.setData({ url })
  },
})
