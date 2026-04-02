import { useState } from 'react';
import { Card, Button, Space, Typography } from 'antd';
import { ShoppingCartOutlined, ExclamationCircleOutlined, DownOutlined, RightOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const BooksNotFound = ({ books, onRecommend }) => {
  if (!books || books.length === 0) {
    return null;
  }

  const [expanded, setExpanded] = useState(false);

  const handleRecommend = (book) => {
    if (onRecommend) {
      onRecommend(book.title, book.author);
    }
  };

  return (
    <Card
      style={{
        marginTop: 16,
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #e8e8e8'
      }}
      bodyStyle={{ padding: expanded ? 24 : 0 }}
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#1677ff' }} />
          <span style={{ color: '#262626' }}>以下书籍暂无现售</span>
        </Space>
      }
      extra={
        <Button
          type="link"
          size="small"
          icon={expanded ? <DownOutlined /> : <RightOutlined />}
          onClick={() => setExpanded(!expanded)}
          style={{ padding: 0 }}
        >
          {expanded ? '收起' : '展开'}
        </Button>
      }
    >
      {expanded && (
        <div>
          {books.map((book, index) => (
            <div
              key={index}
              style={{
                padding: '8px 12px',
                borderBottom: index < books.length - 1 ? '1px solid #f0f0f0' : 'none',
                background: '#f5f5f5',
                borderRadius: 4,
                marginBottom: 8
              }}
            >
              <div style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4, color: '#262626' }}>
                      《{book.title}》
                    </div>
                    {book.author && (
                      <div style={{ fontSize: 13, color: '#1677ff' }}>
                        {book.author}
                      </div>
                    )}
                  </div>
                  <Button
                    type="primary"
                    icon={<ShoppingCartOutlined />}
                    size="small"
                    onClick={() => handleRecommend(book)}
                  >
                    荐购
                  </Button>
                </div>
                <Button
                  type="primary"
                  icon={<ShoppingCartOutlined />}
                  size="small"
                  onClick={() => handleRecommend(book)}
                >
                  订购
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

export default BooksNotFound;
