// 存储工具类
// 处理本地存储

const STORAGE_KEYS = {
  SESSION_ID: 'book_agent_session_id',
  USER_ID: 'book_agent_user_id',
  MESSAGES: 'book_agent_messages',
}

class StorageService {
  // 保存会话ID
  setSessionId(sessionId: string) {
    try {
      wx.setStorageSync(STORAGE_KEYS.SESSION_ID, sessionId)
      console.log('保存会话ID:', sessionId)
    } catch (error) {
      console.error('保存会话ID失败:', error)
    }
  }

  // 获取会话ID
  getSessionId(): string | null {
    try {
      return wx.getStorageSync(STORAGE_KEYS.SESSION_ID) || null
    } catch (error) {
      console.error('获取会话ID失败:', error)
      return null
    }
  }

  // 清除会话ID
  clearSessionId() {
    try {
      wx.removeStorageSync(STORAGE_KEYS.SESSION_ID)
      console.log('已清除会话ID')
    } catch (error) {
      console.error('清除会话ID失败:', error)
    }
  }

  // 保存用户ID
  setUserId(userId: string) {
    try {
      wx.setStorageSync(STORAGE_KEYS.USER_ID, userId)
      console.log('保存用户ID:', userId)
    } catch (error) {
      console.error('保存用户ID失败:', error)
    }
  }

  // 获取用户ID
  getUserId(): string | null {
    try {
      return wx.getStorageSync(STORAGE_KEYS.USER_ID) || null
    } catch (error) {
      console.error('获取用户ID失败:', error)
      return null
    }
  }

  // 保存消息历史
  setMessages(messages: any[]) {
    try {
      wx.setStorageSync(STORAGE_KEYS.MESSAGES, JSON.stringify(messages))
    } catch (error) {
      console.error('保存消息历史失败:', error)
    }
  }

  // 获取消息历史
  getMessages(): any[] {
    try {
      const messagesStr = wx.getStorageSync(STORAGE_KEYS.MESSAGES)
      return messagesStr ? JSON.parse(messagesStr) : []
    } catch (error) {
      console.error('获取消息历史失败:', error)
      return []
    }
  }

  // 清除所有数据
  clearAll() {
    try {
      wx.removeStorageSync(STORAGE_KEYS.SESSION_ID)
      wx.removeStorageSync(STORAGE_KEYS.USER_ID)
      wx.removeStorageSync(STORAGE_KEYS.MESSAGES)
      console.log('已清除所有存储数据')
    } catch (error) {
      console.error('清除存储数据失败:', error)
    }
  }
}

// 导出单例
export const storageService = new StorageService()
