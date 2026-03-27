import { useState } from 'react';
import { Card, Collapse, Spin, Typography } from 'antd';
import { BulbOutlined, LoadingOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Panel } = Collapse;

const ThinkingBox = ({ content, isThinking = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!content && !isThinking) {
    return null;
  }

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        background: '#f5f5f5',
        borderRadius: 8,
        border: 'none'
      }}
      bodyStyle={{ padding: 12 }}
    >
      <Collapse
        ghost
        defaultActiveKey={['1']}
        onChange={(keys) => setIsExpanded(keys.includes('1'))}
      >
        <Panel
          header={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {isThinking ? (
                <LoadingOutlined style={{ color: '#1890ff' }} />
              ) : (
                <BulbOutlined style={{ color: '#1890ff' }} />
              )}
              <Text strong style={{ fontSize: 13 }}>
                {isThinking ? '正在思考...' : '思考过程'}
              </Text>
            </div>
          }
          key="1"
          showArrow={true}
        >
          <div
            style={{
              fontSize: 13,
              color: '#666',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              fontFamily: 'monospace',
              background: '#fafafa',
              padding: 12,
              borderRadius: 6,
              maxHeight: '300px',
              overflow: 'auto'
            }}
          >
            {content}
          </div>
        </Panel>
      </Collapse>
    </Card>
  );
};

export default ThinkingBox;
