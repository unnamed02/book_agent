// components/books-not-found/books-not-found.ts
Component({
  properties: {
    books: {
      type: Array,
      value: [],
      observer() {
        this.updateDisplayBooks()
      }
    }
  },

  data: {
    expanded: false,
    displayBooks: [] as any[]
  },

  lifetimes: {
    attached() {
      this.updateDisplayBooks()
    }
  },

  methods: {
    updateDisplayBooks() {
      const books = this.properties.books || []
      const displayBooks = this.data.expanded ? books : books.slice(0, 3)
      this.setData({ displayBooks })
    },

    onRecommendTap(e: any) {
      const { title, author } = e.currentTarget.dataset
      this.triggerEvent('recommend', { title, author })
    },

    onToggle() {
      this.setData({ expanded: !this.data.expanded }, () => {
        this.updateDisplayBooks()
      })
    }
  }
})
