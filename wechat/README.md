# 图书推荐助手 - 微信小程序

这是图书推荐助手的微信小程序版本，已将前端React应用的功能完整迁移到微信小程序平台。

## 功能特性

- ✅ 聊天式图书推荐界面
- ✅ 流式响应（SSE）支持
- ✅ Markdown内容渲染
- ✅ 会话管理（自动保存和恢复）
- ✅ 图片代理（解决豆瓣图片防盗链）
- ✅ 新会话功能
- ✅ 消息历史本地存储

## 项目结构

```
wechat/miniprogram/
├── components/
│   └── markdown/          # Markdown渲染组件
│       ├── markdown.ts
│       ├── markdown.wxml
│       ├── markdown.scss
│       └── markdown.json
├── pages/
│   └── index/             # 主聊天页面
│       ├── index.ts
│       ├── index.wxml
│       ├── index.scss
│       └── index.json
├── utils/
│   ├── api.ts            # API请求工具类
│   ├── storage.ts        # 本地存储工具类
│   └── util.ts           # 通用工具函数
├── app.ts                # 应用入口
├── app.json              # 应用配置
└── app.scss              # 全局样式
```

## 开发配置

### 1. 安装依赖

```bash
cd wechat
npm install
```

### 2. 配置后端API地址

编辑 `miniprogram/utils/api.ts`，修改 `baseUrl`：

```typescript
constructor() {
  // 开发环境
  this.baseUrl = 'http://localhost:8000'

  // 生产环境（替换为你的服务器地址）
  // this.baseUrl = 'https://your-domain.com'
}
```

### 3. 配置服务器域名

在微信公众平台配置以下域名白名单：

- **request合法域名**：你的后端API域名（如 `https://your-domain.com`）
- **uploadFile合法域名**：（如需要）
- **downloadFile合法域名**：（如需要）

开发阶段可以在微信开发者工具中勾选"不校验合法域名"。

### 4. 启动开发

1. 启动后端服务：
   ```bash
   cd backend
   python main.py
   ```

2. 打开微信开发者工具
3. 导入项目，选择 `wechat` 目录
4. 开始开发和调试

## 核心功能说明

### 1. API通信（utils/api.ts）

- 使用微信小程序的 `wx.request` 实现HTTP请求
- 支持 `enableChunked` 分块传输，实现SSE流式响应
- 自动处理豆瓣图片代理URL转换

### 2. 本地存储（utils/storage.ts）

- 会话ID（session_id）持久化
- 用户ID（user_id）持久化
- 消息历史本地缓存

### 3. Markdown渲染（components/markdown）

简化版Markdown解析器，支持：
- 标题（h1, h2, h3）
- 段落
- 列表（有序、无序）
- 粗体、斜体
- 图片
- 代码块
- 链接

### 4. 聊天界面（pages/index）

- 消息列表自动滚动
- 流式响应实时更新
- 加载状态动画
- 新会话确认对话框

## 与前端React版本的差异

| 功能 | React版本 | 微信小程序版本 |
|------|----------|---------------|
| UI框架 | Ant Design | 原生WXML+SCSS |
| Markdown渲染 | react-markdown | 自定义组件 |
| HTTP请求 | fetch API | wx.request |
| 本地存储 | localStorage | wx.storage |
| 路由 | React Router | 微信小程序原生 |

## 注意事项

1. **网络请求限制**
   - 微信小程序要求使用HTTPS（开发阶段可关闭校验）
   - 需要在公众平台配置服务器域名白名单

2. **SSE流式响应**
   - 使用 `enableChunked: true` 启用分块传输
   - 通过 `onChunkReceived` 监听数据流

3. **图片加载**
   - 豆瓣图片需要通过后端代理
   - 使用 `lazy-load` 优化性能

4. **性能优化**
   - 消息列表使用虚拟滚动（可选）
   - 图片懒加载
   - 避免频繁 setData

## 调试技巧

1. **查看网络请求**
   - 微信开发者工具 -> 调试器 -> Network

2. **查看本地存储**
   - 微信开发者工具 -> 调试器 -> Storage

3. **查看日志**
   - 微信开发者工具 -> 调试器 -> Console

4. **真机调试**
   - 微信开发者工具 -> 预览 -> 扫码真机调试

## 发布上线

1. 完善小程序信息（名称、图标、描述等）
2. 配置生产环境API地址
3. 配置服务器域名白名单
4. 微信开发者工具 -> 上传代码
5. 微信公众平台 -> 提交审核
6. 审核通过后发布

## 常见问题

### Q: 请求失败，提示"不在以下 request 合法域名列表中"
A: 需要在微信公众平台配置服务器域名，或在开发工具中勾选"不校验合法域名"。

### Q: 图片无法显示
A: 检查后端的图片代理接口是否正常工作。

### Q: SSE流式响应不工作
A: 确保使用 `enableChunked: true` 并正确处理 `onChunkReceived` 回调。

### Q: 如何清除本地缓存
A: 调用 `storageService.clearAll()` 或在开发工具中手动清除Storage。

## 技术支持

如有问题，请查看：
- 微信小程序官方文档：https://developers.weixin.qq.com/miniprogram/dev/
- 项目后端文档：../README.md
