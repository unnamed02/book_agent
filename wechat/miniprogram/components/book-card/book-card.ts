// components/book-card/book-card.ts
Component({
  properties: {
    books: {
      type: Array,
      value: []
    }
  },

  data: {
    currentPage: 0
  },

  methods: {
    onSwiperChange(e: any) {
      this.setData({
        currentPage: e.detail.current
      })
    },

    onResourceTap(e: any) {
      const url = e.currentTarget.dataset.url
      if (!url) return

      wx.showModal({
        title: '打开链接',
        content: '是否要打开此链接？',
        confirmText: '打开',
        cancelText: '复制',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({
              url: `/pages/webview/webview?url=${encodeURIComponent(url)}`,
              fail: () => {
                this.copyLink(url)
              }
            })
          } else if (res.cancel) {
            this.copyLink(url)
          }
        }
      })
    },

    copyLink(url: string) {
      wx.setClipboardData({
        data: url,
        success: () => {
          wx.showToast({
            title: '链接已复制',
            icon: 'success'
          })
        }
      })
    },

    onRecommendTap(e: any) {
      const { title, author } = e.currentTarget.dataset
      this.triggerEvent('recommend', { title, author })
    }
  }
})
