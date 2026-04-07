module.exports = {
  apps: [
    {
      name: 'book-backend',
      cwd: './backend',
      script: 'uvicorn',
      // 生产环境：使用 4 个 worker 进程（可根据 CPU 核心数调整）
      // 试用阶段推荐：2-4 workers，支持 100-200 并发
      args: 'api:app --host 0.0.0.0 --port 8000 --workers 4',
      interpreter: 'python3',
      env: {
        NODE_ENV: 'production',
        // 限制每个 worker 的内存使用
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/backend-error.log',
      out_file: './logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',  // 4 workers * 500MB ≈ 2GB
      // 优雅关闭，等待请求处理完成
      kill_timeout: 5000,
      // 启动延迟，避免同时启动导致资源争抢
      exp_backoff_restart_delay: 100,
    },
    // 注意：React 前端已停止维护，如需启动请手动运行
    // {
    //   name: 'book-frontend',
    //   cwd: './frontend',
    //   script: 'npm',
    //   args: 'run dev',
    //   env: { NODE_ENV: 'production' },
    //   max_memory_restart: '500M',
    // },
  ],
};
