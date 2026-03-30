// components/book-card/book-card.ts
Component({
  properties: {
    books: {
      type: Array,
      value: []
    }
  },

  data: {
    currentPage: 0,
    safeBooks: [] as any[]
  },

  observers: {
    'books': function(newBooks: any) {
      // 确保 books 始终是数组
      this.setData({
        safeBooks: Array.isArray(newBooks) ? newBooks : []
      })
    }
  },

  methods: {
    onSwiperChange(e: any) {
      this.setData({
        currentPage: e.detail.current
      })
    },

    onRecommendTap(e: any) {
      const { title, author } = e.currentTarget.dataset
      this.triggerEvent('recommend', { title, author })
    },

    onStoreLinkTap(e: any) {
      const url = e.currentTarget.dataset.url
      if (!url) return
      
      wx.showModal({
        title: '提示',
        content: '即将打开网店页面',
        confirmText: '打开',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({
              url: `/pages/webview/webview?url=${encodeURIComponent(url)}`
            })
          }
        }
      })
    }
  }
})
