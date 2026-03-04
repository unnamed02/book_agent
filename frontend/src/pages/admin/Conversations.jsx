import { useState } from 'react';
import { Input, Button, Spin, Empty, message, List, Drawer, Collapse, Tag } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import axios from 'axios';

function AdminConversations() {
  const [loading, setLoading] = useState(false);
  const [searchUserId, setSearchUserId] = useState('');
  const [conversations, setConversations] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [sessionDetails, setSessionDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  const apiBaseUrl = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : `http://${window.location.hostname}:8001`;

  const handleSearch = async () => {
    if (!searchUserId.trim()) {
      message.warning('请输入用户ID');
      return;
    }

    try {
      setLoading(true);
      const response = await axios.get(`${apiBaseUrl}/conversations/${searchUserId}`, {
        params: {
          page: 1,
          page_size: pagination.pageSize
        }
      });

      setConversations(response.data.sessions || []);
      setHasSearched(true);
    } catch (error) {
      console.error('获取对话历史失败:', error);
      message.error('获取对话历史失败，请检查用户ID');
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewSession = async (session) => {
    setSelectedSession(session);
    setDrawerVisible(true);
    await fetchSessionDetails(session.session_id);
  };

  const fetchSessionDetails = async (sessionId) => {
    try {
      setDetailsLoading(true);
      const response = await axios.get(`${apiBaseUrl}/conversations/session/${sessionId}`);
      setSessionDetails(response.data);
    } catch (error) {
      console.error('获取会话详情失败:', error);
      message.error('获取会话详情失败');
    } finally {
      setDetailsLoading(false);
    }
  };

  const renderMessageContent = (msg) => {
    if (typeof msg === 'object') {
      if (msg.type === 'human' || msg.role === 'user') {
        return `用户: ${msg.content || msg.text || ''}`;
      } else if (msg.type === 'ai' || msg.role === 'assistant') {
        return `助手: ${msg.content || msg.text || ''}`;
      }
    }
    return String(msg);
  };

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
        <Input
          placeholder="输入用户ID查询对话历史"
          prefix={<SearchOutlined />}
          value={searchUserId}
          onChange={(e) => setSearchUserId(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: '400px' }}
        />
        <Button
          type="primary"
          onClick={handleSearch}
          loading={loading}
        >
          查询
        </Button>
      </div>

      <Spin spinning={loading}>
        {hasSearched ? (
          conversations.length > 0 ? (
            <List
              dataSource={conversations}
              renderItem={(session) => (
                <List.Item
                  key={session.session_id}
                  style={{
                    padding: '12px',
                    border: '1px solid #f0f0f0',
                    borderRadius: '4px',
                    marginBottom: '8px'
                  }}
                >
                  <List.Item.Meta
                    title={
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span>会话 ID: {session.session_id.substring(0, 20)}...</span>
                        <Tag color="blue">{session.messages_count} 条消息</Tag>
                      </div>
                    }
                    description={
                      <div style={{ color: '#666', fontSize: '12px' }}>
                        <div>创建时间: {new Date(session.created_at).toLocaleString('zh-CN')}</div>
                        <div>最后活跃: {new Date(session.last_active_at).toLocaleString('zh-CN')}</div>
                      </div>
                    }
                  />
                  <Button
                    type="link"
                    onClick={() => handleViewSession(session)}
                  >
                    查看详情
                  </Button>
                </List.Item>
              )}
            />
          ) : (
            <Empty description={`未找到用户 ${searchUserId} 的对话历史`} />
          )
        ) : (
          <Empty description="请输入用户ID查询对话历史" />
        )}
      </Spin>

      <Drawer
        title={`会话详情 - ${selectedSession?.session_id?.substring(0, 20)}...`}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={600}
      >
        {detailsLoading ? (
          <Spin />
        ) : sessionDetails ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>用户ID</div>
              <div style={{ wordBreak: 'break-all', fontSize: '12px', fontFamily: 'monospace' }}>
                {sessionDetails.user_id}
              </div>
            </div>

            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>创建时间</div>
              <div>{new Date(sessionDetails.created_at).toLocaleString('zh-CN')}</div>
            </div>

            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>最后活跃</div>
              <div>{new Date(sessionDetails.last_active_at).toLocaleString('zh-CN')}</div>
            </div>

            {sessionDetails.messages && sessionDetails.messages.length > 0 ? (
              <div style={{
                marginTop: '16px',
                paddingTop: '16px',
                borderTop: '1px solid #f0f0f0'
              }}>
                <div style={{
                  color: '#666',
                  fontSize: '12px',
                  marginBottom: '8px',
                  fontWeight: 'bold'
                }}>
                  消息列表 ({sessionDetails.messages.length} 条)
                </div>

                <div style={{
                  maxHeight: '400px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}>
                  {sessionDetails.messages.map((msg, idx) => {
                    const isUser = msg.type === 'human' || msg.role === 'user';
                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '8px 12px',
                          borderRadius: '4px',
                          background: isUser ? '#e6f4ff' : '#f6f6f6',
                          wordBreak: 'break-word',
                          fontSize: '12px'
                        }}
                      >
                        <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '11px', color: '#666' }}>
                          {isUser ? '用户' : '助手'}
                        </div>
                        <div>{renderMessageContent(msg)}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <Empty description="暂无消息" style={{ marginTop: '16px' }} />
            )}
          </div>
        ) : (
          <Empty />
        )}
      </Drawer>
    </div>
  );
}

export default AdminConversations;
