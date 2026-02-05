# 微信小程序配置指南

## 快速开始

### 1. 修改API地址

打开 `miniprogram/utils/api.ts`，找到第15行左右：

```typescript
constructor() {
  // 开发环境 - 本地测试
  this.baseUrl = 'http://localhost:8000'

  // 生产环境 - 部署后使用（取消注释并修改为你的域名）
  // this.baseUrl = 'https://your-domain.com'
}
```

**开发阶段**：保持 `http://localhost:8000`，并在微信开发者工具中：
- 点击右上角"详情"
- 勾选"不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书"

**生产环境**：
1. 将后端部署到服务器（必须支持HTTPS）
2. 修改 `baseUrl` 为你的域名，如 `https://api.example.com`
3. 在微信公众平台配置服务器域名白名单

### 2. 配置服务器域名（生产环境必需）

登录[微信公众平台](https://mp.weixin.qq.com/)：

1. 进入"开发" -> "开发管理" -> "开发设置"
2. 找到"服务器域名"
3. 添加以下域名：
   - **request合法域名**：`https://your-domain.com`（你的后端API域名）

注意：
- 域名必须使用HTTPS
- 域名需要备案
- 每月只能修改5次

### 3. 测试连接

在小程序中发送一条消息，检查：
- 开发者工具 Console 是否有错误
- Network 标签页是否显示请求成功
- 是否收到后端响应

## 环境切换

建议使用环境变量来管理不同环境的配置：

```typescript
// miniprogram/utils/api.ts
constructor() {
  // 根据编译模式自动切换
  const isDev = __wxConfig.envVersion === 'develop'
  this.baseUrl = isDev
    ? 'http://localhost:8000'  // 开发环境
    : 'https://your-domain.com' // 生产环境
}
```

## 常见问题

**Q: 提示"不在以下 request 合法域名列表中"**
- 开发阶段：勾选"不校验合法域名"
- 生产环境：在公众平台配置域名白名单

**Q: 请求超时**
- 检查后端服务是否启动
- 检查防火墙是否开放端口
- 检查API地址是否正确

**Q: 图片无法显示**
- 确保后端 `/proxy-image` 接口正常
- 检查图片URL是否正确代理
