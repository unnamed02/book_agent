import { Card, Button, Tag, Typography } from 'antd';
import { ReadOutlined, ShoppingCartOutlined, ShopOutlined, LinkOutlined } from '@ant-design/icons';

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
              <span>现售书籍</span>
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
                    {currentBook.author && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        作者: {currentBook.author}
                      </div>
                    )}
                    {item.pub_info && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        {item.pub_info}
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                      <div style={{ fontSize: 12, color: '#1677ff' }}>
                        位置: {item.location} | 架号: {item.shelf_number}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14, color: '#f5222d', fontWeight: 500 }}>
                          ¥{item.discount_price || item.price}
                        </span>
                        {item.discount && item.discount_price && item.price && (
                          <span style={{ fontSize: 11, color: '#999', textDecoration: 'line-through' }}>
                            ¥{item.price}
                          </span>
                        )}
                      </div>
                    </div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      <Tag 
                        size="small" 
                        style={{ 
                          background: item.stock > 0 ? '#e6f4ff' : '#f5f5f5',
                          color: item.stock > 0 ? '#1677ff' : '#999',
                          border: 'none'
                        }}
                      >
                        {item.stock > 0 ? '有货' : '缺货'}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                        库存{item.stock}本
                      </Text>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 网店在售 */}
        {currentBook.hasOnlineStores && currentBook.onlineStores && currentBook.onlineStores.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4, color: '#262626', fontSize: 13 }}>
              <ShopOutlined style={{ color: '#1677ff' }} />
              <span>网店在售</span>
            </div>
            <div>
              {currentBook.onlineStores.map((store, index) => (
                <div 
                  key={index}
                  style={{ 
                    padding: '8px 0', 
                    borderBottom: index < currentBook.onlineStores.length - 1 ? '1px solid #f0f0f0' : 'none' 
                  }}
                >
                  <div style={{ width: '100%' }}>
                    {store.title && (
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>{store.title}</div>
                    )}
                    {currentBook.author && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        作者: {currentBook.author}
                      </div>
                    )}
                    {store.pub_info && (
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                        {store.pub_info}
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <Tag size="small" style={{ background: '#e6f4ff', color: '#1677ff', border: 'none', fontSize: 11 }}>
                        {store.source}
                      </Tag>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12, color: '#f5222d', fontWeight: 500 }}>
                          ¥{store.discount_price || store.price}
                        </span>
                        {store.discount && store.discount_price && store.price && (
                          <span style={{ fontSize: 10, color: '#999', textDecoration: 'line-through' }}>
                            ¥{store.price}
                          </span>
                        )}
                      </div>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                      <Button
                        type="link"
                        size="small"
                        onClick={() => window.open(store.link, '_blank')}
                        style={{ padding: 0, fontSize: 12 }}
                      >
                        查看详情 &gt;
                      </Button>
                      <Button
                        type="primary"
                        size="small"
                        onClick={() => window.open(store.link, '_blank')}
                        style={{ fontSize: 12 }}
                      >
                        下单
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 读者订购按钮 */}
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4, color: '#262626', fontSize: 13 }}>
            <ShoppingCartOutlined style={{ color: '#1677ff' }} />
            <span>读者订购</span>
          </div>
          <div style={{ padding: 8, background: '#f5f5f5', borderRadius: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 10, color: '#666' }}>
                  缺货可提交订购申请
                </div>
              </div>
              <Button
                type="primary"
                icon={<ShoppingCartOutlined />}
                size="small"
                onClick={() => handleRecommend(currentBook)}
              >
                订购
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default BookCard;
