import { Card, Button, Tag, Typography } from 'antd';
import { ReadOutlined, LinkOutlined, ShoppingCartOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const BookCard = ({ books, onRecommend }) => {
  const getApiBaseUrl = () => {
    return window.location.hostname === 'localhost'
      ? 'http://localhost:8000'
      : `http://${window.location.hostname}:8000`;
  };

  if (!books || books.length === 0) {
    return null;
  }

  const currentBook = books[0];

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

  return (
    <div className="book-card-container">
      <style>{`
        .book-card-container .ant-card-body::-webkit-scrollbar {
          width: 4px;
        }
        .book-card-container .ant-card-body::-webkit-scrollbar-track {
          background: transparent;
        }
        .book-card-container .ant-card-body::-webkit-scrollbar-thumb {
          background: #ccc;
          border-radius: 2px;
        }
        .book-card-container .ant-card-body::-webkit-scrollbar-thumb:hover {
          background: #999;
        }
      `}</style>

      {/* 书籍卡片 */}
      <Card
        size="small"
        style={{
          background: '#fff',
          borderRadius: 12,
          maxHeight: 540,
          border: '1px solid #e8e8e8',
          overflow: 'hidden'
        }}
        styles={{ 
          body: { 
            padding: 12,
            maxHeight: 540,
            overflow: 'auto',
            scrollbarWidth: 'thin',
            scrollbarColor: '#ccc transparent'
          } 
        }}
      >
        {/* 书籍封面和基本信息 */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          {currentBook.image && (
            <img
              src={`${getApiBaseUrl()}/proxy-image?url=${encodeURIComponent(currentBook.image)}`}
              alt={currentBook.title}
              style={{
                width: 80,
                height: 110,
                objectFit: 'cover',
                borderRadius: 6,
                flexShrink: 0
              }}
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <Title level={5} style={{ margin: 0, marginBottom: 4, fontSize: 14 }}>
              《{currentBook.title}》
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>
              {currentBook.author || '作者未知'}
            </Text>
            {currentBook.publisher && currentBook.publisher !== '未知' && (
              <Tag size="small" style={{ marginBottom: 4, background: '#e6f4ff', color: '#1677ff', border: 'none', fontSize: 10 }}>
                {currentBook.publisher}
              </Tag>
            )}
            {currentBook.rating && (
              <Tag size="small" style={{ marginBottom: 4, background: '#e6f4ff', color: '#1677ff', border: 'none', fontSize: 10 }}>
                {currentBook.rating}分
              </Tag>
            )}
          </div>
        </div>

        {/* 推荐理由 */}
        {currentBook.reason && (
          <div style={{ marginBottom: 12, padding: 8, background: '#f5f5f5', borderRadius: 6 }}>
            <Text style={{ fontSize: 12, color: '#666' }}>推荐理由：</Text>
            <Text style={{ fontSize: 12 }}>{currentBook.reason}</Text>
          </div>
        )}

        {/* 馆藏信息 */}
        {currentBook.hasLibrary && currentBook.libraryItems && currentBook.libraryItems.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4, color: '#262626', fontSize: 13 }}>
              <ReadOutlined style={{ color: '#1677ff' }} />
              <span>馆藏信息</span>
            </div>
            <div>
              {currentBook.libraryItems.map((item, index) => (
                <div 
                  key={index}
                  style={{ 
                    padding: '8px 0', 
                    borderBottom: index < currentBook.libraryItems.length - 1 ? '1px solid #f0f0f0' : 'none' 
                  }}
                >
                  <div style={{ width: '100%' }}>
                    {item.title && (
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>{item.title}</div>
                    )}
                    {item.pub_info && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        {item.pub_info}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: '#1677ff' }}>
                      索书号: {item.call_number} | {item.location}
                    </div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      <Tag 
                        size="small" 
                        style={{ 
                          background: item.available > 0 ? '#e6f4ff' : '#f5f5f5',
                          color: item.available > 0 ? '#1677ff' : '#999',
                          border: 'none'
                        }}
                      >
                        {item.status}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                        馆藏{item.total}册，可借{item.available}册
                      </Text>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 电子资源 */}
        {currentBook.hasResources && currentBook.resources && currentBook.resources.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4, color: '#262626', fontSize: 13 }}>
              <LinkOutlined style={{ color: '#1677ff' }} />
              <span>电子资源</span>
            </div>
            {currentBook.resources.map((platform, idx) => (
              <div key={idx} style={{ marginBottom: 8 }}>
                <div 
                  style={{ 
                    fontSize: 11, 
                    marginBottom: 4, 
                    fontWeight: 500,
                    color: '#666'
                  }}
                >
                  [{platform.source}]
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {platform.books?.map((resource, ridx) => (
                    <div
                      key={ridx}
                      onClick={() => handleResourceClick(resource.link)}
                      style={{ 
                        cursor: 'pointer',
                        padding: '6px 8px',
                        background: '#f5f5f5',
                        borderRadius: 4
                      }}
                    >
                      <div style={{ fontSize: 12, color: '#1677ff' }}>{resource.title}</div>
                      {(resource.author || resource.publisher) && (
                        <div style={{ fontSize: 10, color: '#1677ff' }}>
                          {resource.author} {resource.publisher}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 荐购按钮 */}
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4, color: '#262626', fontSize: 13 }}>
            <ShoppingCartOutlined style={{ color: '#1677ff' }} />
            <span>图书荐购</span>
          </div>
          <div style={{ padding: 8, background: '#f5f5f5', borderRadius: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 10, color: '#666' }}>
                  可提交荐购申请
                </div>
              </div>
              <Button
                type="primary"
                icon={<ShoppingCartOutlined />}
                size="small"
                onClick={() => handleRecommend(currentBook)}
              >
                荐购
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default BookCard;
