import { Card, List, Tag, Space, Typography } from 'antd';
import { SearchOutlined, LinkOutlined } from '@ant-design/icons';

const { Text } = Typography;

const SearchResults = ({ results, onResultClick }) => {
  if (!results || results.length === 0) {
    return null;
  }

  const handleClick = (result) => {
    if (onResultClick) {
      onResultClick(result.url, result.title);
    } else if (result.url) {
      window.open(result.url, '_blank');
    }
  };

  return (
    <Card
      size="small"
      style={{
        marginTop: 12,
        background: '#f0f5ff',
        borderRadius: 8,
        border: '1px solid #d6e4ff'
      }}
      title={
        <Space>
          <SearchOutlined style={{ color: '#1890ff' }} />
          <Text strong style={{ fontSize: 13 }}>
            已阅读 {results.length} 个页面
          </Text>
        </Space>
      }
    >
      <List
        size="small"
        dataSource={results}
        renderItem={(item, index) => (
          <List.Item
            style={{
              padding: '8px 0',
              cursor: 'pointer',
              borderBottom: index < results.length - 1 ? '1px solid #e8e8e8' : 'none'
            }}
            onClick={() => handleClick(item)}
          >
            <Space>
              <Tag color="blue" size="small">[{item.index}]</Tag>
              <Text
                style={{
                  fontSize: 13,
                  color: '#1890ff',
                  textDecoration: 'underline'
                }}
              >
                {item.title}
              </Text>
              <LinkOutlined style={{ fontSize: 12, color: '#999' }} />
            </Space>
          </List.Item>
        )}
      />
    </Card>
  );
};

export default SearchResults;
