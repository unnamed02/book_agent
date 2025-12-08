import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Avatar, Space, Typography } from 'antd';
import { SendOutlined, BookOutlined, UserOutlined } from '@ant-design/icons';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

const ImageComponent = ({ src, alt }) => {
  const [error, setError] = useState(false);
  if (error) return null;
  return <img src={src} alt={alt} onError={() => setError(true)} />;
};

const { TextArea } = Input;
const { Title, Text } = Typography;

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        message: input,
        session_id: sessionId
      });

      // 保存session_id
      if (response.data.session_id) {
        setSessionId(response.data.session_id);
      }

      setMessages(prev => [...prev, { role: 'assistant', content: response.data.response }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后再试。'
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: '100vh', background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ width: '100%', maxWidth: '900px', height: '90vh' }}>
        <Card
          styles={{ body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }}
          style={{
            borderRadius: '16px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            overflow: 'hidden',
            border: 'none',
            height: '100%'
          }}
        >
          {/* Header */}
          <div style={{
            padding: '16px 24px',
            borderBottom: '1px solid #f0f0f0',
            background: '#fff'
          }}>
            <Space>
              <Avatar icon={<BookOutlined />} style={{ background: '#1677ff' }} />
              <Title level={4} style={{ margin: 0 }}>图书推荐助手</Title>
            </Space>
          </div>

          {/* Messages */}
          <div style={{
            padding: '24px',
            flex: 1,
            overflowY: 'auto',
            background: '#fafafa'
          }}>
            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', marginTop: '120px' }}>
                <BookOutlined style={{ fontSize: '64px', color: '#d9d9d9', marginBottom: '16px' }} />
                <Title level={3} style={{ color: '#595959' }}>你好！我是图书推荐助手</Title>
                <Text type="secondary">告诉我你想读什么类型的书，我会为你推荐</Text>
              </div>
            ) : (
              <Space vertical size={24} style={{ width: '100%' }}>
                {messages.map((msg, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '12px' }}>
                    <Avatar
                      icon={msg.role === 'user' ? <UserOutlined /> : <BookOutlined />}
                      style={{
                        background: msg.role === 'user' ? '#1677ff' : '#f0f0f0',
                        color: msg.role === 'user' ? '#fff' : '#595959',
                        flexShrink: 0
                      }}
                    />
                    <div style={{ flex: 1, paddingTop: '4px' }}>
                      {msg.role === 'assistant' ? (
                        <Card
                          size="small"
                          style={{
                            background: '#fff',
                            borderRadius: '12px',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                            border: 'none'
                          }}
                        >
                          <div className="markdown-content">
                            <ReactMarkdown components={{ img: ImageComponent }}>{msg.content}</ReactMarkdown>
                          </div>
                        </Card>
                      ) : (
                        <Card
                          size="small"
                          style={{
                            background: '#e6f4ff',
                            borderRadius: '12px',
                            display: 'inline-block',
                            maxWidth: '80%',
                            border: 'none'
                          }}
                        >
                          <Text>{msg.content}</Text>
                        </Card>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <Avatar icon={<BookOutlined />} style={{ background: '#f0f0f0', color: '#595959' }} />
                    <Card
                      size="small"
                      loading
                      style={{
                        background: '#fff',
                        borderRadius: '12px',
                        width: '200px',
                        border: 'none'
                      }}
                    >
                      正在思考...
                    </Card>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </Space>
            )}
          </div>

          {/* Input */}
          <div style={{
            padding: '16px 24px',
            borderTop: '1px solid #f0f0f0',
            background: '#fff'
          }}>
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="输入消息..."
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={loading}
                style={{
                  borderRadius: '12px',
                  resize: 'none'
                }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={sendMessage}
                loading={loading}
                disabled={!input.trim()}
                style={{
                  height: 'auto',
                  borderRadius: '12px',
                  marginLeft: '8px'
                }}
              >
                发送
              </Button>
            </Space.Compact>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default App;
