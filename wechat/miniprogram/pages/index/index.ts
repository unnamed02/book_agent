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
  thinkingContent?: string  // 思考过程内容
  isThinking?: boolean      // 是否正在思考
  searchResults?: any[]     // 搜索结果
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
    isUserScrolling: false,
    currentRequestTask: null as any,
  },

  scrollTimer: null as number | null,
  lastScrollTime: 0,
  lastScrollTop: 0,

  onLoad() {
    // 恢复会话信息
    const sessionId = storageService.getSessionId()
    const userId = storageService.getUserId()

    if (sessionId) {
      this.setData({ sessionId })
    }

    if (userId) {
      this.setData({ userId })
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

    const requestTask = apiService.sendChatMessage(
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
          currentRequestTask: null,
        })
      },
      // onComplete
      () => {
        this.setData({ loading: false, currentRequestTask: null })

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

    this.setData({ currentRequestTask: requestTask })
  },

  // 停止生成
  async onStopGeneration() {
    const { currentRequestTask, messages, sessionId } = this.data

    // 先通知后端停止生成
    if (sessionId) {
      try {
        await apiService.stopChat({ session_id: sessionId })
      } catch (e) {
        console.error('通知后端停止失败:', e)
      }
    }

    // 中断前端请求
    if (currentRequestTask) {
      try {
        currentRequestTask.abort()
      } catch (e) {
        console.error('中断请求失败:', e)
      }
    }

    // 标记最后一条助手消息为非流式
    const newMessages = [...messages]
    if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
      newMessages[newMessages.length - 1] = {
        ...newMessages[newMessages.length - 1],
        isStreaming: false,
      }
    }

    this.setData({
      loading: false,
      currentRequestTask: null,
      messages: newMessages,
    })
    storageService.setMessages(newMessages)
  },

  // AI推荐：分析这本书哪个版本好
  onAIRecommend(e: any) {
    const { title, author } = e.detail
    if (!title) return

    const messageContent = author
      ? `《${title}》（${author}著）哪个出版社的什么版本好？`
      : `《${title}》哪个出版社的什么版本好？`

    this.sendAIQuestion(messageContent, '推荐失败，请重试')
  },

  // AI导读：生成书籍导读
  onAIRead(e: any) {
    const { title, author } = e.detail
    if (!title) return

    const messageContent = author
      ? `请为《${title}》（${author}著）生成一份AI导读，包括：核心观点、内容框架、适合人群、阅读建议。`
      : `请为《${title}》生成一份AI导读，包括：核心观点、内容框架、适合人群、阅读建议。`

    this.sendAIQuestion(messageContent, '导读生成失败，请重试')
  },

  // 通用AI提问方法
  sendAIQuestion(messageContent: string, errorToast: string) {
    const userMessage: Message = {
      role: 'user',
      content: messageContent,
    }

    const messages = [...this.data.messages, userMessage]
    this.setData({ messages, loading: true, canSend: false })
    this.scrollToBottom()

    let currentContent = ''
    let hasCreatedMessage = false

    const requestTask = apiService.sendChatMessage(
      {
        message: userMessage.content,
        session_id: this.data.sessionId || undefined,
        user_id: this.data.userId || undefined,
      },
      (data: SSEData) => {
        this.handleSSEMessage(data, (content: string) => {
          currentContent = content
          hasCreatedMessage = this.updateAssistantMessage(content, hasCreatedMessage, true)
        })
      },
      (error: any) => {
        console.error('AI请求失败:', error)
        wx.showToast({ title: errorToast, icon: 'none' })
        const errorMessage: Message = {
          role: 'assistant',
          content: '抱歉，发生了错误。请稍后再试。',
          isStreaming: false,
        }
        this.setData({ messages: [...this.data.messages, errorMessage], loading: false, currentRequestTask: null })
      },
      () => {
        this.setData({ loading: false, currentRequestTask: null })
        if (hasCreatedMessage) {
          const messages = this.data.messages
          messages[messages.length - 1].isStreaming = false
          this.setData({ messages })
        }
        storageService.setMessages(this.data.messages)
      }
    )

    this.setData({ currentRequestTask: requestTask })
  },

  // 处理SSE消息
  handleSSEMessage(data: SSEData, updateContent: (content: string) => void) {
    if (data.type === 'busy') {
      // 当前有正在进行的对话
      wx.showToast({ title: data.content || '请稍后再试', icon: 'none' })
      this.setData({ loading: false, currentRequestTask: null })
      return
    } else if (data.type === 'session') {
      // 保存会话信息
      if (data.session_id) {
        this.setData({ sessionId: data.session_id })
        storageService.setSessionId(data.session_id)
      }
      if (data.user_id) {
        this.setData({ userId: data.user_id })
        storageService.setUserId(data.user_id)
      }
    } else if (data.type === 'thinking') {
      // 思考过程流式输出
      const messages = this.data.messages
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        const lastMessage = messages[messages.length - 1]
        const newThinkingContent = (lastMessage.thinkingContent || '') + (data.content || '')
        const newMessages = [...messages]
        newMessages[newMessages.length - 1] = {
          ...lastMessage,
          thinkingContent: newThinkingContent,
          isThinking: true
        }
        this.setData({ messages: newMessages })
        this.scrollToBottom()
      } else {
        // 创建新的助手消息，包含思考内容
        const assistantMessage: Message = {
          role: 'assistant',
          content: '',
          thinkingContent: data.content || '',
          isThinking: true,
          isStreaming: true
        }
        this.setData({
          messages: [...this.data.messages, assistantMessage]
        })
        this.scrollToBottom()
      }
    } else if (data.type === 'search_results') {
      // 搜索结果
      const messages = this.data.messages
      const searchResults = Array.isArray(data.content) ? data.content : []

      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        // 如果已有助手消息，更新它
        const lastMessage = messages[messages.length - 1]
        const newMessages = [...messages]
        newMessages[newMessages.length - 1] = {
          ...lastMessage,
          searchResults: searchResults
        }
        this.setData({ messages: newMessages })
      } else {
        // 如果还没有助手消息，创建一个新的
        const assistantMessage: Message = {
          role: 'assistant',
          content: '',
          searchResults: searchResults,
          isStreaming: true
        }
        this.setData({
          messages: [...this.data.messages, assistantMessage]
        })
      }
      this.scrollToBottom()
    } else if (data.type === 'token') {
      // 流式 token - 逐字追加
      const messages = this.data.messages
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        // 已有助手消息，直接追加内容
        const lastMessage = messages[messages.length - 1]
        // 当开始输出正文时，标记思考结束
        if (lastMessage.isThinking) {
          lastMessage.isThinking = false
        }
        const newContent = lastMessage.content + (data.content || '')
        const newMessages = [...messages]
        newMessages[newMessages.length - 1] = {
          ...lastMessage,
          content: newContent,
          isThinking: false
        }
        this.setData({ messages: newMessages })
        this.scrollToBottom()
      } else {
        // 如果还没有助手消息，创建一个
        updateContent(data.content || '')
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
    } else if (data.type === 'purchase_form') {
      // 荐购表单 - 显示 purchase-form 组件
      const messages = this.data.messages
      const purchaseData = data.content || {}
      
      // 如果最后一条消息是 AI 消息，合并表单数据到该消息
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        const lastMessage = messages[messages.length - 1]
        messages[messages.length - 1] = {
          ...lastMessage,
          type: 'purchase_form',
          purchaseTitle: purchaseData.title || '',
          purchaseAuthor: purchaseData.author || ''
        }
      } else {
        // 没有 AI 消息时，创建新消息
        const purchaseMessage: Message = {
          role: 'assistant',
          type: 'purchase_form',
          content: '',
          purchaseTitle: purchaseData.title || '',
          purchaseAuthor: purchaseData.author || ''
        }
        messages.push(purchaseMessage)
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
    } else if (data.type === 'content_blocked') {
      // 内容被审核拦截，移除已渲染的助手消息，显示错误提示
      const messages = this.data.messages
      // 移除最后一条正在流式输出的助手消息
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        messages.pop()
      }
      // 添加错误提示消息
      messages.push({
        role: 'assistant',
        content: data.content || '抱歉，生成的内容可能不符合相关法律政策规定，试试别的问题吧',
        isStreaming: false
      })
      this.setData({ messages, loading: false })
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

  // 滚动到底部（仅在用户未手动滚动时，300ms节流）
  scrollToBottom() {
    if (this.data.isUserScrolling) return
    const now = Date.now()
    if (now - this.lastScrollTime < 300) return
    this.lastScrollTime = now

    const messages = this.data.messages
    if (messages.length > 0) {
      this.setData({ scrollToView: `msg-${messages.length - 1}` })
    }
  },

  // 监听滚动事件：用户一旦向上滑动，判定为主动阅读
  onScroll(e: any) {
    const scrollTop = e.detail.scrollTop || 0
    if (this.data.isUserScrolling) {
      this.lastScrollTop = scrollTop
      return
    }
    if (this.lastScrollTop > 0 && scrollTop < this.lastScrollTop) {
      this.setData({ isUserScrolling: true })
    }
    this.lastScrollTop = scrollTop
  },

  // 滚动到底部时触发，恢复自动滚动
  onScrollToLower() {
    this.setData({ isUserScrolling: false })
  },

  // 处理搜索结果点击
  onSearchResultTap(e: any) {
    const url = e.currentTarget.dataset.url
    const title = e.currentTarget.dataset.title
    if (!url) return

    wx.showModal({
      title: title || '打开链接',
      content: url,
      confirmText: '打开',
      cancelText: '复制',
      success: (res) => {
        if (res.confirm) {
          // 打开链接
          wx.navigateTo({
            url: `/pages/webview/webview?url=${encodeURIComponent(url)}`,
            fail: () => {
              // 如果没有 webview 页面，则复制链接
              wx.setClipboardData({
                data: url,
                success: () => {
                  wx.showToast({
                    title: '链接已复制',
                    icon: 'success',
                    duration: 2000,
                  })
                },
              })
            },
          })
        } else if (res.cancel) {
          // 复制链接
          wx.setClipboardData({
            data: url,
            success: () => {
              wx.showToast({
                title: '链接已复制',
                icon: 'success',
                duration: 2000,
              })
            },
          })
        }
      },
    })
  },

  // 开始新会话
  startNewSession() {
    wx.showModal({
      title: '提示',
      content: '确定要开始新会话吗？当前对话将被删除。',
      success: (res) => {
        if (res.confirm) {
          // 清空当前会话（后端会自动归档旧会话）
          this.setData({
            messages: [],
            sessionId: null,
          })
          storageService.clearSessionId()
          storageService.setMessages([])
        }
      },
    })
  },

  // 处理荐购按钮点击
  async onRecommend(e: any) {
    const { title, author } = e.detail
    const { sessionId, userId } = this.data

    // 生成用户消息内容
    const messageContent = `荐购 ${title} ${author || ''}`

    // 立即发送消息到后端保存
    try {
      const result = await apiService.saveMessage({
        message: messageContent,
        session_id: sessionId || undefined,
        user_id: userId || undefined
      })

      // 后端返回的 session_id 和 user_id
      if (result.success) {
        if (result.session_id) {
          this.setData({ sessionId: result.session_id })
          storageService.setSessionId(result.session_id)
        }
        if (result.user_id) {
          this.setData({ userId: result.user_id })
          storageService.setUserId(result.user_id)
        }
      }
    } catch (error) {
      console.error('保存消息失败:', error)
      // 继续显示消息，即使保存失败
    }

    // 添加用户消息
    const userMessage: Message = {
      role: 'user',
      content: messageContent
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
      storageService.setMessages(messages)
      this.scrollToBottom()
    }
  },
})
