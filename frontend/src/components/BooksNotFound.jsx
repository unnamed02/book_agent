import { Card, List, Button, Space, Typography, Tag } from 'antd';
import { BookOutlined, ShoppingOutlined, ExclamationCircleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const BooksNotFound = ({ books, onRecommend }) => {
  if (!books || books.length === 0) {
    return null;
  }

  const handleRecommend = (book) => {
    if (onRecommend) {
      onRecommend(book.title, book.author);
    }
  };

  return (
    <Card
      style={{
        marginTop: 16,
        background: '#fffbe6',
        borderRadius: 12,
        border: '1px solid #ffe58f'
      }}
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#faad14' }} />
          <span>以下书籍暂无馆藏和电子资源</span>
        </Space>
      }
    >
      <List
        dataSource={books}
        renderItem={(book, index) => (
          <List.Item
            style={{
              padding: '12px 0',
              borderBottom: index < books.length - 1 ? '1px solid #f0f0f0' : 'none'
            }}
          >
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>
                    《{book.title}》
                  </div>
                  {book.author && (
                    <div style={{ fontSize: 13, color: '#666' }}>
                      {book.author}
                    </div>
                  )}
                </div>
                <Button
                  type="primary"
                  icon={<ShoppingOutlined />}
                  size="small"
                  onClick={() => handleRecommend(book)}
                >
                  荐购
                </Button>
              </div>
            </div>
          </List.Item>
        )}
      />
    </Card>
  );
};

export default BooksNotFound;
