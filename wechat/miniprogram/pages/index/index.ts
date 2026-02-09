// index.ts
import { apiService } from '../../utils/api'
import { storageService } from '../../utils/storage'
import type { SSEData } from '../../utils/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
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
    } else if (data.type === 'dialogue') {
      // 对话内容 - 处理图片代理
      const processedContent = apiService.proxyImageUrls(data.content || '')
      const content = processedContent + '\n\n'
      updateContent(content)
    } else if (data.type === 'books') {
      // 书单 - 处理图片代理
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]
      const processedContent = apiService.proxyImageUrls(data.content || '')
      const newContent = lastMessage.content + processedContent + '\n\n'
      updateContent(newContent)
    } else if (data.type === 'status') {
      // 状态信息
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]
      const newContent = lastMessage.content + `*${data.content}*\n\n`
      updateContent(newContent)
    } else if (data.type === 'book_detail') {
      // 书籍详情
      const messages = this.data.messages
      const lastMessage = messages[messages.length - 1]
      // 移除"正在查询"状态
      let newContent = lastMessage.content.replace(/\*正在为您查询这些书籍的详细信息\.\.\.\*\n\n/g, '')
      // 添加详细信息（已经过代理URL处理）
      const processedContent = apiService.proxyImageUrls(data.content || '')
      newContent += processedContent + '\n\n'
      updateContent(newContent)
    } else if (data.type === 'message') {
      // 简单消息 - 处理图片代理
      const processedContent = apiService.proxyImageUrls(data.content || '')
      updateContent(processedContent)
    } else if (data.type === 'done') {
      // 完成
      this.setData({ loading: false })
    }

    this.scrollToBottom()
  },

  // 更新助手消息
  updateAssistantMessage(content: string, hasCreated: boolean, isStreaming: boolean): boolean {
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
      messages[messages.length - 1] = {
        ...messages[messages.length - 1],
        content,
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
})
