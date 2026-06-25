// PM2 集群配置 — 多核并行，支撑 5000+ 并发
module.exports = {
  apps: [
    {
      name: 'queue-system',
      script: './server.js',
      instances: 'max', // 自动匹配 CPU 核数
      exec_mode: 'cluster',
      env: {
        PORT: 3000,
        ADMIN_PASSWORD: 'admin888',
      },
      // 自动重启保护
      max_memory_restart: '512M',
      // 日志
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      merge_logs: true,
    },
  ],
};
