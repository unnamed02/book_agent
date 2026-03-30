import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Avatar, Space, Typography, Tooltip, message as antMessage } from 'antd';
import { SendOutlined, BookOutlined, UserOutlined, PlusOutlined, SettingOutlined } from '@ant-design/icons';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 导入新组件
import BookCard from './components/BookCard';
import BookGallery from './components/BookGallery';
import PurchaseForm from './components/PurchaseForm';
import BooksNotFound from './components/BooksNotFound';
import ThinkingBox from './components/ThinkingBox';
import SearchResults from './components/SearchResults';

const ImageComponent = ({ src, alt }) => {
  const [error, setError] = useState(false);
  if (error) return null;
  return <img src={src} alt={alt} onError={() => setError(true)} />;
};

// 自定义加粗文本组件 - 点击可复制
const StrongComponent = ({ children }) => {
  const handleClick = (e) => {
    e.preventDefault();
    const text = e.target.innerText;
    navigator.clipboard.writeText(text).then(() => {
      // 显示复制成功提示
      const target = e.target;
      const originalText = target.innerText;
      target.innerText = '已复制!';
      target.style.color = '#52c41a';
      setTimeout(() => {
        target.innerText = originalText;
        target.style.color = '';
      }, 1000);
    }).catch(err => {
      console.error('复制失败:', err);
    });
  };

  return (
    <strong
      onClick={handleClick}
      style={{
        cursor: 'pointer',
        userSelect: 'none',
        transition: 'all 0.2s'
      }}
      title="点击复制"
    >
      {children}
    </strong>
  );
};

const { TextArea } = Input;
const { Title, Text } = Typography;

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [userId, setUserId] = useState(null);
  const [isUserScrolling, setIsUserScrolling] = useState(false);
  const messagesEndRef = useRef(null);
  const scrollTimerRef = useRef(null);

  const scrollToBottom = () => {
    if (!isUserScrolling) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初始化时从 localStorage 恢复 session_id、user_id 和消息历史
  useEffect(() => {
    const savedSessionId = localStorage.getItem('book_agent_session_id');
    const savedUserId = localStorage.getItem('book_agent_user_id');
    const savedMessages = localStorage.getItem('book_agent_messages');

    if (savedSessionId) {
      setSessionId(savedSessionId);
      console.log('恢复会话:', savedSessionId);
    }

    if (savedUserId) {
      setUserId(savedUserId);
      console.log('恢复用户ID:', savedUserId);
    }

    if (savedMessages) {
      try {
        const parsedMessages = JSON.parse(savedMessages);
        // 标记所有消息为非流式状态
        const restoredMessages = parsedMessages.map(msg => ({
          ...msg,
          isStreaming: false
        }));
        setMessages(restoredMessages);
        console.log('恢复消息历史:', restoredMessages.length, '条');
      } catch (e) {
        console.error('恢复消息历史失败:', e);
      }
    }
  }, []);

  // 保存消息到 localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('book_agent_messages', JSON.stringify(messages));
    }
  }, [messages]);

  // 滚动控制
  const handleScroll = () => {
    setIsUserScrolling(true);
    if (scrollTimerRef.current) {
      clearTimeout(scrollTimerRef.current);
    }
    scrollTimerRef.current = setTimeout(() => {
      setIsUserScrolling(false);
    }, 2000);
  };

  // 清理定时器
  useEffect(() => {
    return () => {
      if (scrollTimerRef.current) {
        clearTimeout(scrollTimerRef.current);
      }
    };
  }, []);

  // 获取API基础URL
  const getApiBaseUrl = () => {
    return window.location.hostname === 'localhost'
      ? 'http://localhost:8000'
      : `http://${window.location.hostname}:8000`;
  };

  // 将豆瓣图片URL替换为代理URL
  const proxyImageUrls = (content) => {
    const apiBaseUrl = getApiBaseUrl();
    // 匹配markdown图片格式：![alt](http(s)://img*.doubanio.com/...) 或其他豆瓣域名
    return content.replace(
      /!\[(.*?)\]\((https?:\/\/[^)]*douban[^)]*\.(com|net)\/[^)]+)\)/g,
      (_match, alt, imageUrl) => {
        const proxyUrl = `${apiBaseUrl}/proxy-image?url=${encodeURIComponent(imageUrl)}`;
        return `![${alt}](${proxyUrl})`;
      }
    );
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    const currentInput = input;
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // 使用当前域名和协议，兼容本地和远程部署
      const apiBaseUrl = getApiBaseUrl();

      const response = await fetch(`${apiBaseUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentInput,
          session_id: sessionId,
          user_id: userId
        }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentContent = '';
      let fullContent = ''; // 完整内容（用于最终保存）
      let hasCreatedMessage = false; // 标记是否已创建assistant消息

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // 保留不完整的行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'session') {
                // 保存会话信息
                if (data.session_id) {
                  setSessionId(data.session_id);
                  localStorage.setItem('book_agent_session_id', data.session_id);
                  console.log('保存会话ID:', data.session_id);
                }
                if (data.user_id) {
                  setUserId(data.user_id);
                  localStorage.setItem('book_agent_user_id', data.user_id);
                  console.log('保存用户ID:', data.user_id);
                }
              } else if (data.type === 'token') {
                // Token 流式输出
                currentContent += data.content;
                fullContent += data.content;

                if (!hasCreatedMessage) {
                  setMessages(prev => [...prev, { role: 'assistant', content: currentContent, isStreaming: true }]);
                  hasCreatedMessage = true;
                  setLoading(false);  // 关闭加载动画
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      content: currentContent
                    };
                    return newMessages;
                  });
                }
              } else if (data.type === 'dialogue') {
                // 对话部分 - 第一次有内容时创建消息
                currentContent = data.content + '\n\n';
                fullContent += currentContent;

                if (!hasCreatedMessage) {
                  setMessages(prev => [...prev, { role: 'assistant', content: currentContent, isStreaming: true }]);
                  hasCreatedMessage = true;
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      content: currentContent
                    };
                    return newMessages;
                  });
                }
              } else if (data.type === 'books') {
                // 书单部分
                currentContent += data.content + '\n\n';
                fullContent += data.content + '\n\n';

                if (!hasCreatedMessage) {
                  setMessages(prev => [...prev, { role: 'assistant', content: currentContent, isStreaming: true }]);
                  hasCreatedMessage = true;
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      content: currentContent
                    };
                    return newMessages;
                  });
                }
              } else if (data.type === 'status') {
                // 状态信息（正在查询...）
                currentContent += `*${data.content}*\n\n`;

                if (!hasCreatedMessage) {
                  setMessages(prev => [...prev, { role: 'assistant', content: currentContent, isStreaming: true }]);
                  hasCreatedMessage = true;
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      content: currentContent
                    };
                    return newMessages;
                  });
                }
              } else if (data.type === 'book_detail') {
                // 移除"正在查询"的状态信息
                currentContent = currentContent.replace(/\*正在为您查询这些书籍的详细信息\.\.\.\*\n\n/g, '');

                // 添加详细信息，并将豆瓣图片URL替换为代理URL
                const processedContent = proxyImageUrls(data.content);
                currentContent += processedContent + '\n\n';
                fullContent += processedContent + '\n\n';
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1] = {
                    ...newMessages[newMessages.length - 1],
                    content: currentContent
                  };
                  return newMessages;
                });
              } else if (data.type === 'message') {
                // 简单消息（如澄清问题）
                currentContent = data.content;
                fullContent = data.content;

                if (!hasCreatedMessage) {
                  setMessages(prev => [...prev, { role: 'assistant', content: currentContent, isStreaming: true }]);
                  hasCreatedMessage = true;
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      content: currentContent
                    };
                    return newMessages;
                  });
                }
              } else if (data.type === 'thinking') {
                // 思考过程
                setMessages(prev => {
                  const newMessages = [...prev];
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                    const lastMsg = newMessages[newMessages.length - 1];
                    newMessages[newMessages.length - 1] = {
                      ...lastMsg,
                      thinkingContent: (lastMsg.thinkingContent || '') + data.content,
                      isThinking: true
                    };
                  } else {
                    newMessages.push({
                      role: 'assistant',
                      content: '',
                      thinkingContent: data.content,
                      isThinking: true,
                      isStreaming: true
                    });
                    hasCreatedMessage = true;
                    setLoading(false);  // 关闭加载动画
                  }
                  return newMessages;
                });
              } else if (data.type === 'search_results') {
                // 搜索结果
                setMessages(prev => {
                  const newMessages = [...prev];
                  const searchResults = Array.isArray(data.content) ? data.content : [];
                  
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                    // 如果已有助手消息，更新它
                    const lastMsg = newMessages[newMessages.length - 1];
                    newMessages[newMessages.length - 1] = {
                      ...lastMsg,
                      searchResults: searchResults
                    };
                  } else {
                    // 如果还没有助手消息，创建一个新的
                    newMessages.push({
                      role: 'assistant',
                      content: '',
                      searchResults: searchResults,
                      isStreaming: true
                    });
                    hasCreatedMessage = true;
                    setLoading(false);  // 关闭加载动画
                  }
                  return newMessages;
                });
              } else if (data.type === 'book_cards') {
                // 书籍卡片
                setMessages(prev => {
                  const newMessages = [...prev];
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                    const lastMsg = newMessages[newMessages.length - 1];
                    newMessages[newMessages.length - 1] = {
                      ...lastMsg,
                      type: 'book_cards',
                      books: data.content || [],
                      isStreaming: false
                    };
                  } else {
                    newMessages.push({
                      role: 'assistant',
                      content: '',
                      type: 'book_cards',
                      books: data.content || [],
                      isStreaming: false
                    });
                    hasCreatedMessage = true;
                  }
                  return newMessages;
                });
              } else if (data.type === 'purchase_form') {
                // 读者订购表单
                setMessages(prev => {
                  const newMessages = [...prev];
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                    const lastMsg = newMessages[newMessages.length - 1];
                    newMessages[newMessages.length - 1] = {
                      ...lastMsg,
                      type: 'purchase_form',
                      purchaseTitle: data.content?.title || '',
                      purchaseAuthor: data.content?.author || '',
                      isStreaming: false
                    };
                  } else {
                    newMessages.push({
                      role: 'assistant',
                      content: '',
                      type: 'purchase_form',
                      purchaseTitle: data.content?.title || '',
                      purchaseAuthor: data.content?.author || '',
                      isStreaming: false
                    });
                    hasCreatedMessage = true;
                  }
                  return newMessages;
                });
              } else if (data.type === 'books_not_found') {
                // 未找到的书籍
                setMessages(prev => {
                  const newMessages = [...prev];
                  if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
                    const lastMsg = newMessages[newMessages.length - 1];
                    newMessages[newMessages.length - 1] = {
                      ...lastMsg,
                      booksNotFound: data.content || []
                    };
                  } else {
                    newMessages.push({
                      role: 'assistant',
                      content: '',
                      booksNotFound: data.content || [],
                      isStreaming: false
                    });
                    hasCreatedMessage = true;
                  }
                  return newMessages;
                });
              } else if (data.type === 'done') {
                // 完成，标记为非流式，并立即关闭 loading
                setLoading(false);  // 立即关闭加载状态
                if (hasCreatedMessage) {
                  // 清理状态消息
                  const finalContent = (currentContent || fullContent).replace(/\*正在.*\.\.\.\*\n\n/g, '');
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = {
                      ...newMessages[newMessages.length - 1],
                      isStreaming: false,
                      content: finalContent
                    };
                    return newMessages;
                  });
                }
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e, line);
            }
          }
        }
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后再试。',
        isStreaming: false
      }]);
    } finally {
      setLoading(false);
    }
  };

  // 开始新会话
  const startNewSession = () => {
    setMessages([]);
    setSessionId(null);
    localStorage.removeItem('book_agent_session_id');
    localStorage.removeItem('book_agent_messages');
    console.log('已清除会话，开始新对话');
  };

  // 处理订购按钮点击
  const handleRecommend = (title, author) => {
    const newMessage = {
      role: 'assistant',
      type: 'purchase_form',
      content: '',
      purchaseTitle: title,
      purchaseAuthor: author
    };
    setMessages(prev => [...prev, newMessage]);
  };

  // 处理订购表单提交
  const handlePurchaseSubmit = (values) => {
    console.log('订购提交:', values);
    antMessage.success('订购申请已提交！');
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
            background: '#fff',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <Space>
              <Avatar icon={<BookOutlined />} style={{ background: '#1677ff' }} />
              <Title level={4} style={{ margin: 0 }}>咸阳市新华书店AI店员</Title>
            </Space>
            <Space>
              {messages.length > 0 && (
                <Tooltip title="清除当前会话，开始新对话">
                  <Button
                    icon={<PlusOutlined />}
                    onClick={startNewSession}
                    disabled={loading}
                  >
                    新会话
                  </Button>
                </Tooltip>
              )}
              <Tooltip title="进入管理后台">
                <Button
                  type="text"
                  icon={<SettingOutlined />}
                  onClick={() => window.location.href = '/admin'}
                />
              </Tooltip>
            </Space>
          </div>

          {/* Messages */}
          <div
            style={{
              padding: '24px',
              flex: 1,
              overflowY: 'auto',
              background: '#fafafa'
            }}
            onScroll={handleScroll}
          >
            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', marginTop: '120px' }}>
                <BookOutlined style={{ fontSize: '64px', color: '#d9d9d9', marginBottom: '16px' }} />
                <Title level={3} style={{ color: '#595959' }}>您好！我是咸阳市新华书店AI店员</Title>
                <Text type="secondary">告诉我您想读什么类型的书，我会为您推荐</Text>
              </div>
            ) : (
              <Space orientation="vertical" size={24} style={{ width: '100%', display: 'flex' }}>
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
                        <div>
                          {/* 思考过程 */}
                          {msg.thinkingContent && (
                            <ThinkingBox
                              content={msg.thinkingContent}
                              isThinking={msg.isThinking}
                            />
                          )}

                          {/* 普通 Markdown 内容 */}
                          {msg.content && (
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
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{ img: ImageComponent }}
                                >
                                  {msg.content}
                                </ReactMarkdown>
                              </div>
                            </Card>
                          )}

                          {/* 搜索来源 */}
                          {msg.searchResults && msg.searchResults.length > 0 && (
                            <SearchResults results={msg.searchResults} />
                          )}

                          {/* 书籍卡片 - 画廊效果 */}
                          {msg.type === 'book_cards' && msg.books && (
                            <BookGallery
                              books={msg.books}
                              onRecommend={handleRecommend}
                            />
                          )}

                          {/* 未找到的书籍 */}
                          {msg.booksNotFound && msg.booksNotFound.length > 0 && (
                            <BooksNotFound
                              books={msg.booksNotFound}
                              onRecommend={handleRecommend}
                            />
                          )}

                          {/* 读者订购表单 */}
                          {msg.type === 'purchase_form' && (
                            <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
                              <PurchaseForm
                                title={msg.purchaseTitle}
                                author={msg.purchaseAuthor}
                                onSubmit={handlePurchaseSubmit}
                              />
                            </div>
                          )}
                        </div>
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
