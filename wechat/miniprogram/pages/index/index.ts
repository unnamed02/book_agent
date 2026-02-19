// index.ts
import { apiService } from '../../utils/api'
import { storageService } from '../../utils/storage'
import type { SSEData } from '../../utils/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  type?: 'book_cards' | 'text' | 'books_not_found' | 'purchase_form'
  books?: any[]
  booksNotFound?: any[]
  appendContent?: string
  purchaseTitle?: string
  purchaseAuthor?: string
}

Page({
  data: {
    messages: [] as Message[],
    input: '',
    loading: false,
    sessionId: null as string | null,
    userId: null as string | null,
    scrollToView: '',
    canSend: false,
  },

  onLoad() {
    // 恢复会话信息
    const sessionId = storageService.getSessionId()
    const userId = storageService.getUserId()

    if (sessionId) {
      this.setData({ sessionId })
      console.log('恢复会话:', sessionId)
    }

    if (userId) {
      this.setData({ userId })
      console.log('恢复用户ID:', userId)
    }

    // 可选：恢复消息历史
    const messages = storageService.getMessages()
    if (messages.length > 0) {
      this.setData({ messages })
    }
  },

  // 输入框变化
  onInput(e: any) {
    const value = e.detail.value
    this.setData({
      input: value,
      canSend: value.trim().length > 0,
    })
  },

  // 发送消息
  sendMessage() {
    const { input, loading, sessionId, userId } = this.data

    if (!input.trim() || loading) {
      return
    }

    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
    }

    const messages = [...this.data.messages, userMessage]
    this.setData({
      messages,
      input: '',
      loading: true,
      canSend: false,
    })

    // 滚动到底部
    this.scrollToBottom()

    // 发送请求
    let currentContent = ''
    let hasCreatedMessage = false

    apiService.sendChatMessage(
      {
        message: userMessage.content,
        session_id: sessionId || undefined,
        user_id: userId || undefined,
      },
      // onMessage
      (data: SSEData) => {
        this.handleSSEMessage(data, (content: string) => {
          currentContent = content
          hasCreatedMessage = this.updateAssistantMessage(content, hasCreatedMessage, true)
        })
      },
      // onError
      (error: any) => {
        console.error('发送消息失败:', error)
        wx.showToast({
          title: '发送失败，请重试',
          icon: 'none',
        })

        const errorMessage: Message = {
          role: 'assistant',
          content: '抱歉，发生了错误。请稍后再试。',
          isStreaming: false,
        }

        this.setData({
          messages: [...this.data.messages, errorMessage],
          loading: false,
        })
      },
      // onComplete
      () => {
        console.log('消息发送完成')
        this.setData({ loading: false })

        // 标记消息为非流式
        if (hasCreatedMessage) {
          const messages = this.data.messages
          messages[messages.length - 1].isStreaming = false
          this.setData({ messages })
        }

        // 保存消息历史
        storageService.setMessages(this.data.messages)
      }
    )
  },

  // 处理SSE消息
  handleSSEMessage(data: SSEData, updateContent: (content: string) => void) {
    if (data.type === 'session') {
      // 保存会话信息
      if (data.session_id) {
        this.setData({ sessionId: data.session_id })
        storageService.setSessionId(data.session_id)
      }
      if (data.user_id) {
        this.setData({ userId: data.user_id })
        storageService.setUserId(data.user_id)
      }
    } else if (data.type === 'message') {
      // 消息内容
      const content = (data.content || '') + '\n\n'

      // 如果消息已创建，需要追加而不是替换
      const messages = this.data.messages
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        const lastMessage = messages[messages.length - 1]
        const newContent = lastMessage.content + content
        updateContent(newContent)
      } else {
        updateContent(content)
      }
    } else if (data.type === 'books') {
      // 书单
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]
      const newContent = lastMessage.content + (data.content || '') + '\n\n'
      updateContent(newContent)
    } else if (data.type === 'status') {
      // 状态信息
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]
      const newContent = lastMessage.content + `*${data.content}*\n\n`
      updateContent(newContent)
    } else if (data.type === 'book_cards') {
      // 书籍卡片数据
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]

      // 如果没有最后一条消息，创建一个新消息
      if (!lastMessage || lastMessage.role !== 'assistant') {
        messages.push({
          role: 'assistant',
          content: '',
          type: 'book_cards',
          books: []
        })
      }

      // 移除"正在查询"状态
      let newContent = lastMessage ? lastMessage.content.replace(/\*正在为您查询这些书籍的详细信息\.\.\.\*\n\n/g, '') : ''

      // 处理图片代理
      const bookCards: any[] = Array.isArray(data.content) ? data.content : []
      const books = bookCards.map((book: any) => ({
        ...book,
        image: book.image ? apiService.proxyImageUrls(book.image) : ''
      }))

      // 更新消息，添加书籍卡片类型标记
      messages[messages.length - 1] = {
        ...messages[messages.length - 1],
        content: newContent,
        type: 'book_cards',
        books: books
      }
      this.setData({ messages })
    } else if (data.type === 'books_not_found') {
      // 未找到的书籍列表 - 合并到上一条消息
      const messages = this.data.messages
      const booksNotFound = Array.isArray(data.content) ? data.content : []

      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        // 合并到上一条助手消息
        const lastMessage = messages[messages.length - 1]

        // 移除"正在查询"状态
        let newContent = lastMessage.content.replace(/\*正在为您查询这些书籍的详细信息\.\.\.\*\n\n/g, '')

        messages[messages.length - 1] = {
          ...lastMessage,
          content: newContent,
          booksNotFound: booksNotFound
        }
      } else {
        // 如果没有上一条消息，创建新消息
        messages.push({
          role: 'assistant',
          type: 'books_not_found',
          booksNotFound: booksNotFound,
          content: ''
        })
      }
      this.setData({ messages })
    } else if (data.type === 'append_message') {
      // 追加消息 - 追加到最后一条消息的 appendContent 字段
      const messages = this.data.messages
      if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1]
        if (lastMessage.role === 'assistant') {
          const processedContent = apiService.proxyImageUrls(data.content || '')
          messages[messages.length - 1] = {
            ...lastMessage,
            appendContent: (lastMessage.appendContent || '') + processedContent
          }
          this.setData({ messages })
        }
      }
    } else if (data.type === 'done') {
      // 完成
      this.setData({ loading: false })
    }

    this.scrollToBottom()
  },

  // 更新助手消息
  updateAssistantMessage(content: string, hasCreated: boolean, isStreaming: boolean, append: boolean = false): boolean {
    const messages = [...this.data.messages]

    if (!hasCreated) {
      // 创建新消息
      messages.push({
        role: 'assistant',
        content,
        isStreaming,
      })
      this.setData({ messages })
      return true
    } else {
      // 更新最后一条消息
      const lastMessage = messages[messages.length - 1]
      messages[messages.length - 1] = {
        ...lastMessage,
        content: append ? (lastMessage.content + content) : content,
        isStreaming,
      }
      this.setData({ messages })
      return true
    }
  },

  // 滚动到底部
  scrollToBottom() {
    const messages = this.data.messages
    if (messages.length > 0) {
      this.setData({
        scrollToView: `msg-${messages.length - 1}`,
      })
    }
  },

  // 开始新会话
  startNewSession() {
    wx.showModal({
      title: '提示',
      content: '确定要开始新会话吗？当前对话将被清空。',
      success: (res) => {
        if (res.confirm) {
          this.setData({
            messages: [],
            sessionId: null,
          })
          storageService.clearSessionId()
          storageService.setMessages([])
          console.log('已清除会话，开始新对话')
        }
      },
    })
  },

  // 处理荐购按钮点击
  onRecommend(e: any) {
    const { title, author } = e.detail

    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content: `荐购 ${title} ${author || ''}`
    }

    // 添加表单消息
    const formMessage: Message = {
      role: 'assistant',
      type: 'purchase_form',
      content: '',
      purchaseTitle: title,
      purchaseAuthor: author
    }

    // 添加两条消息到列表
    const messages = [...this.data.messages, userMessage, formMessage]
    this.setData({ messages })

    // 保存消息历史
    storageService.setMessages(messages)

    // 滚动到底部
    this.scrollToBottom()
  },

  // 处理荐购表单提交
  onPurchaseSubmit(e: any) {
    const { message } = e.detail

    if (message) {
      // 添加助手消息到聊天记录
      const messages = this.data.messages
      messages.push({
        role: 'assistant',
        content: message,
        type: 'text'
      })

      this.setData({ messages })
      storageService.saveMessages(messages)
      this.scrollToBottom()
    }
  },
})
