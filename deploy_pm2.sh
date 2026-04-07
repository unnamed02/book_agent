#!/bin/bash
# PM2 部署脚本

echo "=========================================="
echo "使用 PM2 部署图书推荐系统"
echo "=========================================="

# 创建日志目录
mkdir -p logs

# 停止并删除旧的 PM2 进程
echo "1. 清理旧进程..."
pm2 stop all 2>/dev/null
pm2 delete all 2>/dev/null

# 杀掉可能残留的进程
echo "2. 清理残留进程..."
pkill -f "uvicorn api:app" 2>/dev/null
pkill -f "vite" 2>/dev/null

# 等待进程完全停止
sleep 2

# 使用 ecosystem.config.js 启动服务
echo "3. 启动服务..."
pm2 start ecosystem.config.js

# 保存 PM2 配置
echo "4. 保存 PM2 配置..."
pm2 save

# 设置 PM2 开机自启（可选）
# pm2 startup

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "常用命令："
echo "  pm2 list                - 查看所有进程"
echo "  pm2 logs                - 查看日志"
echo "  pm2 logs book-backend   - 查看后端日志"
echo "  pm2 monit               - 监控面板"
echo "  pm2 restart all         - 重启所有服务"
echo "  pm2 stop all            - 停止所有服务"
echo ""
echo "健康检查："
echo "  curl http://localhost:8000/health"
echo ""
echo "注意事项："
echo "  1. 确保后端地址已配置到小程序服务器域名白名单"
echo "  2. 生产环境必须使用 HTTPS"
echo "  3. 首次部署需要运行: python service/init_knowledge_base.py"
echo ""
echo "=========================================="

# 显示当前状态
pm2 list
