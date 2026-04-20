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

    onResourceTap(e: any) {
      let url = e.currentTarget.dataset.url
      if (!url) return

      // 掌阅链接简化：只保留 bookId 参数
      if (url.includes('zhangyue.com')) {
        const bookIdMatch = url.match(/bookId=(\d+)/)
        if (bookIdMatch) {
          const base = url.split('?')[0]
          url = `${base}?bookId=${bookIdMatch[1]}`
        }
      }

      wx.showModal({
        title: '请复制至浏览器打开',
        content: url,
        confirmText: '复制',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
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
