// API 工具类
// 处理与后端的通信

interface ChatRequest {
  message: string
  session_id?: string
  user_id?: string
}

interface SSEData {
  type: 'session' | 'dialogue' | 'books' | 'status' | 'message' | 'done' | 'book_cards' | 'append_message'
  content?: string
  session_id?: string
  user_id?: string
}

// ArrayBuffer 转字符串的辅助函数 - 支持UTF-8
function arrayBufferToString(buffer: ArrayBuffer): string {
  const uint8Array = new Uint8Array(buffer)
  let result = ''
  let i = 0

  while (i < uint8Array.length) {
    const byte1 = uint8Array[i++]

    // 单字节字符 (0xxxxxxx)
    if (byte1 < 0x80) {
      result += String.fromCharCode(byte1)
    }
    // 双字节字符 (110xxxxx 10xxxxxx)
    else if (byte1 < 0xE0) {
      const byte2 = uint8Array[i++]
      result += String.fromCharCode(((byte1 & 0x1F) << 6) | (byte2 & 0x3F))
    }
    // 三字节字符 (1110xxxx 10xxxxxx 10xxxxxx)
    else if (byte1 < 0xF0) {
      const byte2 = uint8Array[i++]
      const byte3 = uint8Array[i++]
      result += String.fromCharCode(
        ((byte1 & 0x0F) << 12) | ((byte2 & 0x3F) << 6) | (byte3 & 0x3F)
      )
    }
    // 四字节字符 (11110xxx 10xxxxxx 10xxxxxx 10xxxxxx)
    else {
      const byte2 = uint8Array[i++]
      const byte3 = uint8Array[i++]
      const byte4 = uint8Array[i++]
      let codePoint = ((byte1 & 0x07) << 18) | ((byte2 & 0x3F) << 12) |
                      ((byte3 & 0x3F) << 6) | (byte4 & 0x3F)
      codePoint -= 0x10000
      result += String.fromCharCode(0xD800 + (codePoint >> 10))
      result += String.fromCharCode(0xDC00 + (codePoint & 0x3FF))
    }
  }

  return result
}

class ApiService {
  // API 基础 URL - 根据环境自动切换
  baseUrl: string

  constructor() {
    // 微信小程序中需要配置服务器域名
    // 开发环境可以在开发者工具中开启"不校验合法域名"
    this.baseUrl = 'http://localhost:8000' // 默认本地开发
  }

  // 设置 API 基础 URL
  setBaseUrl(url: string) {
    this.baseUrl = url
  }

  // 获取 API 基础 URL
  getBaseUrl(): string {
    return this.baseUrl
  }

  // 将豆瓣图片URL替换为代理URL
  proxyImageUrls(content: string): string {
    // 匹配markdown图片格式：![alt](http(s)://img*.doubanio.com/...) 或其他豆瓣域名
    return content.replace(
      /!\[(.*?)\]\((https?:\/\/[^)]*douban[^)]*\.(com|net)\/[^)]+)\)/g,
      (_match, alt, imageUrl) => {
        const proxyUrl = `${this.baseUrl}/proxy-image?url=${encodeURIComponent(imageUrl)}`
        return `![${alt}](${proxyUrl})`
      }
    )
  }

  // 发送聊天消息（流式响应）
  sendChatMessage(
    request: ChatRequest,
    onMessage: (data: SSEData) => void,
    onError: (error: any) => void,
    onComplete: () => void
  ) {
    const requestTask: any = wx.request({
      url: `${this.baseUrl}/chat/stream`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
      },
      data: request,
      enableChunked: true, // 启用分块传输
      success: (res: any) => {
        console.log('请求成功:', res)
        onComplete()
      },
      fail: (error: any) => {
        console.error('请求失败:', error)
        onError(error)
      },
    } as any)

    // 监听分块数据
    let buffer = ''
    if (requestTask.onChunkReceived) {
      requestTask.onChunkReceived((res: any) => {
        try {
          // 将 ArrayBuffer 转换为字符串
          const chunk = arrayBufferToString(res.data)
          buffer += chunk

          // 按行分割
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || '' // 保留不完整的行

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data: SSEData = JSON.parse(line.slice(6))
                onMessage(data)
              } catch (e) {
                console.error('解析SSE数据失败:', e, line)
              }
            }
          }
        } catch (error) {
          console.error('处理分块数据失败:', error)
        }
      })
    }

    // 监听请求完成
    if (requestTask.onHeadersReceived) {
      requestTask.onHeadersReceived(() => {
        console.log('开始接收数据流')
      })
    }
  }
}

// 导出单例
export const apiService = new ApiService()
export type { ChatRequest, SSEData }
