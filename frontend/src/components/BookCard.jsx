import { useState } from 'react';
import { Card, Button, Tag, Space, Typography, List, Empty } from 'antd';
import { ReadOutlined, LinkOutlined, ShoppingOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const BookCard = ({ books, onRecommend }) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  if (!books || books.length === 0) {
    return null;
  }

  const currentBook = books[currentIndex];

  const handleRecommend = (book) => {
    if (onRecommend) {
      onRecommend(book.title, book.author);
    }
  };

  const handleResourceClick = (url) => {
    if (url) {
      window.open(url, '_blank');
    }
  };

  const goToPrev = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : books.length - 1));
  };

  const goToNext = () => {
    setCurrentIndex((prev) => (prev < books.length - 1 ? prev + 1 : 0));
  };

  return (
    <div style={{ marginTop: 16, background: '#f5f5f5', padding: '16px', borderRadius: 12 }}>
      {/* 导航按钮 */}
      {books.length > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Button type="text" icon={<LeftOutlined />} onClick={goToPrev} size="small">
            上一本
          </Button>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {currentIndex + 1} / {books.length}
          </Text>
          <Button type="text" icon={<RightOutlined />} onClick={goToNext} size="small">
            下一本
          </Button>
        </div>
      )}

      {/* 书籍卡片 */}
      <Card
        size="small"
        style={{
          background: '#fff',
          borderRadius: 12,
          maxHeight: '60vh',
          overflow: 'auto'
        }}
        bodyStyle={{ padding: 16 }}
      >
        {/* 书籍封面和基本信息 */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
          {currentBook.image && (
            <img
              src={currentBook.image}
              alt={currentBook.title}
              style={{
                width: 100,
                height: 140,
                objectFit: 'cover',
                borderRadius: 8,
                flexShrink: 0
              }}
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
          <div style={{ flex: 1 }}>
            <Title level={5} style={{ margin: 0, marginBottom: 8 }}>
              《{currentBook.title}》
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
              {currentBook.author || '作者未知'}
            </Text>
            {currentBook.publisher && currentBook.publisher !== '未知' && (
              <Tag size="small" style={{ marginBottom: 8 }}>
                {currentBook.publisher}
              </Tag>
            )}
            {currentBook.rating && (
              <Tag color="orange" size="small" style={{ marginBottom: 8 }}>
                ⭐ {currentBook.rating}
              </Tag>
            )}
          </div>
        </div>

        {/* 推荐理由 */}
        {currentBook.reason && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f6ffed', borderRadius: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>推荐理由：</Text>
            <Text style={{ fontSize: 13 }}>{currentBook.reason}</Text>
          </div>
        )}

        {/* 馆藏信息 */}
        {currentBook.hasLibrary && currentBook.libraryItems && currentBook.libraryItems.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
              <ReadOutlined />
              <span>馆藏信息</span>
            </div>
            <List
              size="small"
              dataSource={currentBook.libraryItems}
              renderItem={(item) => (
                <List.Item style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ width: '100%' }}>
                    {item.title && (
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>{item.title}</div>
                    )}
                    {item.pub_info && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        {item.pub_info}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: '#666' }}>
                      索书号: {item.call_number} | {item.location}
                    </div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      <Tag
                        color={item.available > 0 ? 'success' : 'error'}
                        size="small"
                      >
                        {item.status}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                        馆藏{item.total}册，可借{item.available}册
                      </Text>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </div>
        )}

        {/* 电子资源 */}
        {currentBook.hasResources && currentBook.resources && currentBook.resources.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
              <LinkOutlined />
              <span>电子资源</span>
            </div>
            {currentBook.resources.map((platform, idx) => (
              <div key={idx} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#1890ff', marginBottom: 8 }}>
                  [{platform.source}]
                </div>
                <Space direction="vertical" style={{ width: '100%' }}>
                  {platform.books?.map((resource, ridx) => (
                    <Button
                      key={ridx}
                      type="link"
                      size="small"
                      onClick={() => handleResourceClick(resource.link)}
                      style={{ textAlign: 'left', padding: 0, height: 'auto' }}
                    >
                      <div>
                        <div style={{ fontSize: 13 }}>{resource.title}</div>
                        {(resource.author || resource.publisher) && (
                          <div style={{ fontSize: 11, color: '#999' }}>
                            {resource.author} {resource.publisher}
                          </div>
                        )}
                      </div>
                    </Button>
                  ))}
                </Space>
              </div>
            ))}
          </div>
        )}

        {/* 荐购按钮 */}
        <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>荐购</div>
              <div style={{ fontSize: 11, color: '#999' }}>
                如需增加馆藏或购买其他版本，可提交荐购申请
              </div>
            </div>
            <Button
              type="primary"
              icon={<ShoppingOutlined />}
              size="small"
              onClick={() => handleRecommend(currentBook)}
            >
              荐购
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default BookCard;
