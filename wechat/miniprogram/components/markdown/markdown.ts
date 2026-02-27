// components/markdown/markdown.ts
// 简单的 Markdown 渲染组件
Component({
  properties: {
    content: {
      type: String,
      value: '',
    },
  },
  data: {
    parsedContent: [] as any[],
  },
  observers: {
    content(newVal: string) {
      this.parseMarkdown(newVal)
    },
  },
  methods: {
    // 解析 Markdown 内容
    parseMarkdown(markdown: string) {
      if (!markdown) {
        this.setData({ parsedContent: [] })
        return
      }

      const lines = markdown.split('\n')
      const parsed: any[] = []
      let inCodeBlock = false
      let codeBlockContent = ''
      let codeBlockLang = ''

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]

        // 代码块处理
        if (line.startsWith('```')) {
          if (inCodeBlock) {
            // 结束代码块
            parsed.push({
              type: 'code',
              content: codeBlockContent.trim(),
              lang: codeBlockLang,
            })
            codeBlockContent = ''
            codeBlockLang = ''
            inCodeBlock = false
          } else {
            // 开始代码块
            inCodeBlock = true
            codeBlockLang = line.slice(3).trim()
          }
          continue
        }

        if (inCodeBlock) {
          codeBlockContent += line + '\n'
          continue
        }

        // 标题处理
        if (line.startsWith('### ')) {
          parsed.push({ type: 'h3', content: line.slice(4) })
        } else if (line.startsWith('## ')) {
          parsed.push({ type: 'h2', content: line.slice(3) })
        } else if (line.startsWith('# ')) {
          parsed.push({ type: 'h1', content: line.slice(2) })
        }
        // 列表处理
        else if (line.match(/^[\d]+\.\s/)) {
          const content = line.replace(/^[\d]+\.\s/, '')
          parsed.push({ type: 'ol', content: this.parseInline(content) })
        } else if (line.match(/^[-*]\s/)) {
          const content = line.replace(/^[-*]\s/, '')
          parsed.push({ type: 'ul', content: this.parseInline(content) })
        }
        // 图片处理
        else if (line.match(/!\[.*?\]\(.*?\)/)) {
          const match = line.match(/!\[(.*?)\]\((.*?)\)/)
          if (match) {
            parsed.push({
              type: 'image',
              alt: match[1],
              src: match[2],
            })
          }
        }
        // 空行
        else if (line.trim() === '') {
          parsed.push({ type: 'br' })
        }
        // 普通段落
        else {
          parsed.push({ type: 'p', content: this.parseInline(line) })
        }
      }

      this.setData({ parsedContent: parsed })
    },

    // 解析行内元素（粗体、斜体、链接、特殊标记等）
    parseInline(text: string): any[] {
      const result: any[] = []
      let current = ''
      let i = 0

      while (i < text.length) {
        // 特殊标记 【text】（版本信息等）
        if (text[i] === '【') {
          if (current) {
            result.push({ type: 'text', content: current })
            current = ''
          }
          const end = text.indexOf('】', i)
          if (end !== -1) {
            result.push({
              type: 'highlight',
              content: text.substring(i + 1, end),
            })
            i = end + 1
            continue
          }
        }
        // 粗体 **text**
        else if (text.substr(i, 2) === '**') {
          if (current) {
            result.push({ type: 'text', content: current })
            current = ''
          }
          const end = text.indexOf('**', i + 2)
          if (end !== -1) {
            result.push({
              type: 'bold',
              content: text.substring(i + 2, end),
            })
            i = end + 2
            continue
          }
        }
        // 斜体 *text*
        else if (text[i] === '*' && text[i + 1] !== '*') {
          if (current) {
            result.push({ type: 'text', content: current })
            current = ''
          }
          const end = text.indexOf('*', i + 1)
          if (end !== -1) {
            result.push({
              type: 'italic',
              content: text.substring(i + 1, end),
            })
            i = end + 1
            continue
          }
        }
        // 链接 [text](url)
        else if (text[i] === '[') {
          const textEnd = text.indexOf(']', i)
          const urlStart = text.indexOf('(', textEnd)
          const urlEnd = text.indexOf(')', urlStart)
          if (textEnd !== -1 && urlStart === textEnd + 1 && urlEnd !== -1) {
            if (current) {
              result.push({ type: 'text', content: current })
              current = ''
            }
            result.push({
              type: 'link',
              text: text.substring(i + 1, textEnd),
              url: text.substring(urlStart + 1, urlEnd),
            })
            i = urlEnd + 1
            continue
          }
        }

        current += text[i]
        i++
      }

      if (current) {
        result.push({ type: 'text', content: current })
      }

      return result
    },

    // 处理图片加载错误
    onImageError(e: any) {
      console.error('图片加载失败:', e)
    },

    // 处理链接点击
    onLinkTap(e: any) {
      const url = e.currentTarget.dataset.url
      if (!url) return

      // 尝试在小程序内打开链接
      wx.showModal({
        title: '打开链接',
        content: '是否要打开此链接？',
        confirmText: '打开',
        cancelText: '复制',
        success: (res) => {
          if (res.confirm) {
            // 用户选择打开链接
            // 注意：需要在 app.json 中配置 web-view 页面
            wx.navigateTo({
              url: `/pages/webview/webview?url=${encodeURIComponent(url)}`,
              fail: () => {
                // 如果没有 webview 页面，则复制链接
                this.copyLink(url)
              },
            })
          } else if (res.cancel) {
            // 用户选择复制链接
            this.copyLink(url)
          }
        },
      })
    },

    // 处理加粗文字点击 - 复制内容
    onBoldTap(e: any) {
      const content = e.currentTarget.dataset.content
      if (!content) return

      wx.setClipboardData({
        data: content,
        success: () => {
          wx.showToast({
            title: '已复制',
            icon: 'success',
            duration: 1500,
          })
        },
        fail: () => {
          wx.showToast({
            title: '复制失败',
            icon: 'none',
            duration: 2000,
          })
        },
      })
    },

    // 处理高亮文字点击 - 复制内容（版本信息等）
    onHighlightTap(e: any) {
      const content = e.currentTarget.dataset.content
      if (!content) return

      wx.setClipboardData({
        data: content,
        success: () => {
          wx.showToast({
            title: '已复制',
            icon: 'success',
            duration: 1500,
          })
        },
        fail: () => {
          wx.showToast({
            title: '复制失败',
            icon: 'none',
            duration: 2000,
          })
        },
      })
    },

    // 复制链接到剪贴板
    copyLink(url: string) {
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
  },
})
