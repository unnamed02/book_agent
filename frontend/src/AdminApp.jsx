import { useState, useEffect } from 'react';
import { Layout, Menu, Breadcrumb, Button, Modal, message } from 'antd';
import {
  DashboardOutlined,
  UserOutlined,
  BookOutlined,
  FileTextOutlined,
  LogoutOutlined
} from '@ant-design/icons';
import AdminDashboard from './pages/admin/Dashboard';
import AdminUsers from './pages/admin/Users';
import AdminRecommendations from './pages/admin/Recommendations';
import AdminConversations from './pages/admin/Conversations';
import ChatApp from './App';

const { Header, Content, Sider } = Layout;

function AdminApp() {
  const [collapsed, setCollapsed] = useState(false);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [showLoginModal, setShowLoginModal] = useState(true);

  // 检查是否已登录
  useEffect(() => {
    const saved = localStorage.getItem('admin_authenticated');
    if (saved) {
      setIsAdmin(true);
      setShowLoginModal(false);
    }
  }, []);

  const handleAdminLogin = async () => {
    // 调用后端验证密码
    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || `http://${window.location.hostname}:8000`;
      const response = await fetch(`${apiBaseUrl}/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: adminPassword })
      });
      const data = await response.json();
      if (data.success) {
        localStorage.setItem('admin_authenticated', 'true');
        localStorage.setItem('admin_token', data.token || '');
        setIsAdmin(true);
        setShowLoginModal(false);
        message.success('登录成功');
      } else {
        message.error(data.message || '密码错误');
      }
    } catch (e) {
      message.error('登录请求失败，请检查网络');
    }
  };

  const handleLogout = () => {
    Modal.confirm({
      title: '确认登出',
      content: '你确定要登出管理界面吗？',
      okText: '确认',
      cancelText: '取消',
      onOk() {
        localStorage.removeItem('admin_authenticated');
        setIsAdmin(false);
        setShowLoginModal(true);
        setAdminPassword('');
      }
    });
  };

  // 如果未登录，显示登录模态框
  if (!isAdmin) {
    return (
      <Modal
        title="管理员登录"
        open={showLoginModal}
        onOk={handleAdminLogin}
        onCancel={() => window.location.href = '/'}
        okText="登录"
        cancelText="返回"
        maskClosable={false}
      >
        <input
          type="password"
          placeholder="请输入管理员密码"
          value={adminPassword}
          onChange={(e) => setAdminPassword(e.target.value)}
          onPressEnter={handleAdminLogin}
          style={{
            width: '100%',
            padding: '8px 12px',
            border: '1px solid #d9d9d9',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        />
      </Modal>
    );
  }

  const menuItems = [
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘'
    },
    {
      key: 'users',
      icon: <UserOutlined />,
      label: '用户管理'
    },
    {
      key: 'recommendations',
      icon: <BookOutlined />,
      label: '荐购管理'
    },
    {
      key: 'conversations',
      icon: <FileTextOutlined />,
      label: '对话历史'
    }
  ];

  const renderContent = () => {
    switch (currentPage) {
      case 'dashboard':
        return <AdminDashboard />;
      case 'users':
        return <AdminUsers />;
      case 'recommendations':
        return <AdminRecommendations />;
      case 'conversations':
        return <AdminConversations />;
      default:
        return <AdminDashboard />;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={(value) => setCollapsed(value)}>
        <div style={{
          height: '64px',
          background: 'rgba(255, 255, 255, 0.2)',
          margin: '16px',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: '18px',
          fontWeight: 'bold'
        }}>
          {!collapsed && '书籍管理'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['dashboard']}
          items={menuItems}
          onClick={(e) => setCurrentPage(e.key)}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <Breadcrumb
            items={[
              { title: '首页' },
              { title: menuItems.find(item => item.key === currentPage)?.label || '仪表盘' }
            ]}
          />
          <Button
            type="text"
            danger
            icon={<LogoutOutlined />}
            onClick={handleLogout}
          >
            登出
          </Button>
        </Header>
        <Content style={{
          margin: '24px 16px',
          padding: '24px',
          background: '#fff',
          borderRadius: '8px',
          minHeight: 'calc(100vh - 112px)'
        }}>
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  );
}

export default AdminApp;
