// components/purchase-form/purchase-form.ts
import { apiService } from '../../utils/api'
import { storageService } from '../../utils/storage'

Component({
  properties: {
    title: {
      type: String,
      value: ''
    },
    author: {
      type: String,
      value: ''
    }
  },

  data: {
    title: '',
    author: '',
    note: '',
    contact: '',
    submitting: false,
    submitted: false  // 是否已提交成功
  },

  methods: {
    onTitleInput(e: any) {
      this.setData({ title: e.detail.value })
    },

    onAuthorInput(e: any) {
      this.setData({ author: e.detail.value })
    },

    onNoteInput(e: any) {
      this.setData({ note: e.detail.value })
    },

    onContactInput(e: any) {
      this.setData({ contact: e.detail.value })
    },

    async onSubmit() {
      const { title, author, note, contact, submitting } = this.data

      // 防止重复提交
      if (submitting) {
        return
      }

      // 验证必填字段
      if (!title || !title.trim()) {
        wx.showToast({
          title: '请输入书名',
          icon: 'none'
        })
        return
      }

      this.setData({ submitting: true })

      try {
        // 获取用户ID
        const userId = storageService.getUserId()
        if (!userId) {
          throw new Error('用户ID不存在')
        }

        // 调用API提交荐购
        const result = await apiService.submitPurchaseRecommendation({
          user_id: userId,
          book_title: title.trim(),
          author: author?.trim() || undefined,
          notes: note?.trim() || undefined,
          contact: contact?.trim() || undefined
        })

        if (result.success) {
          // 标记为已提交
          this.setData({ submitted: true })

          // 显示提交成功提示
          wx.showToast({
            title: '提交成功',
            icon: 'success'
          })

          // 触发提交事件，通知父组件发送消息
          this.triggerEvent('submit', {
            id: result.id,
            title,
            author,
            message: '感谢您的推荐，该书上架会第一时间通知！请问还有什么可以帮您的吗？'
          })
        } else {
          throw new Error(result.message || '提交失败')
        }
      } catch (error: any) {
        console.error('提交荐购失败:', error)
        wx.showToast({
          title: error.message || '提交失败，请重试',
          icon: 'none'
        })
      } finally {
        this.setData({ submitting: false })
      }
    }
  },

  lifetimes: {
    attached() {
      // 初始化时从 properties 复制到 data
      this.setData({
        title: this.properties.title,
        author: this.properties.author
      })
    }
  }
})
