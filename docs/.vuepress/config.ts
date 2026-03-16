import { defineUserConfig } from 'vuepress'
import { viteBundler } from '@vuepress/bundler-vite'
import { defaultTheme } from '@vuepress/theme-default'
import { searchPlugin } from '@vuepress/plugin-search'
import { gitPlugin } from '@vuepress/plugin-git'

export default defineUserConfig({
  lang: 'zh-CN',
  title: 'Book Agent 文档',
  description: 'AI 智能推荐系统',
  base: '/',

  bundler: viteBundler({
    viteOptions: {},
    vuePluginOptions: {},
  }),

  theme: defaultTheme({
    logo: '/logo.svg',
    repo: 'yourorg/book-agent',
    docsBranch: 'main',
    docsDir: 'docs',
    editLinkText: '编辑此页',
    lastUpdatedText: '最后更新',
    contributors: false,
    contributorsText: '贡献者',

    navbar: [
      {
        text: '首页',
        link: '/',
      },
      {
        text: '快速开始',
        link: '/guides/quickstart',
      },
      {
        text: '项目概览',
        children: [
          {
            text: '系统架构',
            link: '/overview/architecture',
          },
          {
            text: '技术栈',
            link: '/overview/tech-stack',
          },
          {
            text: '功能特性',
            link: '/overview/features',
          },
        ],
      },
      {
        text: '开发指南',
        children: [
          {
            text: '环境配置',
            link: '/guides/setup',
          },
          {
            text: '项目结构',
            link: '/guides/project-structure',
          },
        ],
      },
      {
        text: '技术文档',
        children: [
          {
            text: '后端开发',
            children: [
              {
                text: 'LangGraph 工作流',
                link: '/backend/workflow',
              },
              {
                text: '工作流节点',
                link: '/backend/nodes/',
              },
              {
                text: '会话管理系统',
                link: '/backend/session',
              },
              {
                text: '知识库 & RAG',
                link: '/backend/knowledge-base',
              },
            ],
          },
          {
            text: '前端开发',
            children: [
              {
                text: '前端架构',
                link: '/frontend/architecture',
              },
              {
                text: '组件指南',
                link: '/frontend/components',
              },
            ],
          },
          {
            text: 'API 文档',
            link: '/api/endpoints',
          },
        ],
      },
      {
        text: '部署',
        children: [
          {
            text: '生产部署',
            link: '/deployment/production',
          },
          {
            text: '故障排查',
            link: '/deployment/troubleshooting',
          },
        ],
      },
    ],

    sidebar: {
      '/guides/': [
        {
          text: '开发指南',
          children: [
            '/guides/quickstart',
            '/guides/setup',
            '/guides/project-structure',
          ],
        },
      ],
      '/overview/': [
        {
          text: '项目概览',
          children: [
            '/overview/architecture',
            '/overview/tech-stack',
            '/overview/features',
          ],
        },
      ],
      '/backend/': [
        {
          text: '后端开发',
          children: [
            '/backend/workflow',
            '/backend/session',
            '/backend/knowledge-base',
          ],
        },
        {
          text: '工作流节点',
          children: [
            '/backend/nodes/',
            '/backend/nodes/intent-recognition',
            '/backend/nodes/find-book',
            '/backend/nodes/book-info',
            '/backend/nodes/recommendation',
            '/backend/nodes/parse-book-list',
            '/backend/nodes/fetch-details',
            '/backend/nodes/customer-service',
            '/backend/nodes/default',
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 文档',
          children: [
            '/api/endpoints',
            '/api/authentication',
            '/api/error-handling',
          ],
        },
      ],
      '/deployment/': [
        {
          text: '部署指南',
          children: [
            '/deployment/production',
            '/deployment/docker',
            '/deployment/troubleshooting',
          ],
        },
      ],
    },
  }),

  plugins: [
    searchPlugin({
      locales: {
        '/': {
          placeholder: '搜索文档',
        },
      },
    }),
    gitPlugin({
      createdTime: true,
      updatedTime: true,
    }),
  ],
})
