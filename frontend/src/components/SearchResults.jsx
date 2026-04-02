import { useState } from 'react';
import { Card, Tag, Space, Typography } from 'antd';
import { SearchOutlined, LinkOutlined, DownOutlined, RightOutlined } from '@ant-design/icons';

const { Text } = Typography;

const SearchResults = ({ results, onResultClick }) => {
  const [expanded, setExpanded] = useState(true);

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

  const toggleExpand = () => {
    setExpanded(!expanded);
  };

  return (
    <Card
      size="small"
      style={{
        marginTop: 12,
        background: '#fff',
        borderRadius: 8,
        border: '1px solid #e8e8e8'
      }}
      title={
        <Space style={{ cursor: 'pointer' }} onClick={toggleExpand}>
          {expanded ? <DownOutlined style={{ color: '#1677ff', fontSize: 12 }} /> : <RightOutlined style={{ color: '#1677ff', fontSize: 12 }} />}
          <SearchOutlined style={{ color: '#1677ff' }} />
          <Text strong style={{ fontSize: 13, color: '#262626' }}>
            已阅读 {results.length} 个页面
          </Text>
        </Space>
      }
      styles={{ body: { padding: expanded ? 12 : 0, display: expanded ? 'block' : 'none' } }}
    >
      {expanded && (
        <div>
          {results.map((item, index) => (
            <div
              key={index}
              style={{
                padding: '4px 8px',
                cursor: 'pointer',
                borderBottom: index < results.length - 1 ? '1px solid #f0f0f0' : 'none',
                background: 'transparent',
                borderRadius: 4,
                marginBottom: 2
              }}
              onClick={() => handleClick(item)}
            >
              <Space>
                <Tag size="small" style={{ background: '#fff', border: 'none' }}>[{item.index}]</Tag>
                <Text
                  style={{
                    fontSize: 13,
                    color: '#1677ff'
                  }}
                >
                  {item.title}
                </Text>
                <LinkOutlined style={{ fontSize: 12, color: '#1677ff' }} />
              </Space>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

export default SearchResults;
