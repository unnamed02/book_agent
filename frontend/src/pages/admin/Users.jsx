import { useState, useEffect } from 'react';
import { Table, Button, Input, Spin, Empty, message, Drawer } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import axios from 'axios';

function AdminUsers() {
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [searchText, setSearchText] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [userDetails, setUserDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const apiBaseUrl = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : `http://${window.location.hostname}:8001`;

  useEffect(() => {
    fetchUsers();
  }, [pagination.current, pagination.pageSize]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const [usersRes, totalRes] = await Promise.all([
        axios.get(`${apiBaseUrl}/users`, {
          params: {
            page: pagination.current,
            page_size: pagination.pageSize
          }
        }),
        axios.get(`${apiBaseUrl}/users/total`)
      ]);

      setUsers(usersRes.data);
      setTotal(totalRes.data.total);
    } catch (error) {
      console.error('获取用户列表失败:', error);
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchUserDetails = async (userId) => {
    try {
      setDetailsLoading(true);
      const response = await axios.get(`${apiBaseUrl}/users/${userId}`);
      setUserDetails(response.data);
    } catch (error) {
      console.error('获取用户详情失败:', error);
      message.error('获取用户详情失败');
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleViewDetails = (user) => {
    setSelectedUser(user);
    setDrawerVisible(true);
    fetchUserDetails(user.user_id);
  };

  const columns = [
    {
      title: '用户ID',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 200,
      ellipsis: true
    },
    {
      title: '会话数',
      dataIndex: 'session_count',
      key: 'session_count',
      width: 100,
      sorter: (a, b) => a.session_count - b.session_count
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '最后活跃',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (date) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleViewDetails(record)}
        >
          详情
        </Button>
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
        <Input
          placeholder="搜索用户ID"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: '300px' }}
        />
        <Button
          onClick={() => {
            setPagination({ current: 1, pageSize: 20 });
            fetchUsers();
          }}
        >
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={users}
          rowKey="user_id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: total,
            onChange: (page, pageSize) => {
              setPagination({ current: page, pageSize });
            }
          }}
          scroll={{ x: 800 }}
        />
      </Spin>

      <Drawer
        title="用户详情"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={500}
      >
        {detailsLoading ? (
          <Spin />
        ) : userDetails ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>用户ID</div>
              <div style={{ wordBreak: 'break-all' }}>{userDetails.user_id}</div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>会话总数</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1677ff' }}>
                {userDetails.session_count}
              </div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>荐购总数</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#faad14' }}>
                {userDetails.recommendation_count}
              </div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>创建时间</div>
              <div>{new Date(userDetails.created_at).toLocaleString('zh-CN')}</div>
            </div>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>最后活跃</div>
              <div>{new Date(userDetails.updated_at).toLocaleString('zh-CN')}</div>
            </div>
          </div>
        ) : (
          <Empty />
        )}
      </Drawer>
    </div>
  );
}

export default AdminUsers;
