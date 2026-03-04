import { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Spin, Empty, message } from 'antd';
import {
  UserOutlined,
  BookOutlined,
  FileTextOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  CloseOutlined
} from '@ant-design/icons';
import axios from 'axios';

function AdminDashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [recStats, setRecStats] = useState(null);

  const apiBaseUrl = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : `http://${window.location.hostname}:8001`;

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const [systemRes, recRes] = await Promise.all([
        axios.get(`${apiBaseUrl}/stats/system`),
        axios.get(`${apiBaseUrl}/stats/recommendations`)
      ]);

      setStats(systemRes.data);
      setRecStats(recRes.data);
    } catch (error) {
      console.error('获取统计数据失败:', error);
      message.error('无法加载统计数据，请检查API连接');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!stats) {
    return <Empty description="无法加载数据" />;
  }

  return (
    <div>
      <h2 style={{ marginBottom: '24px', fontSize: '20px', fontWeight: 'bold' }}>系统概览</h2>

      {/* 基本统计 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总用户数"
              value={stats.total_users}
              icon={<UserOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总会话数"
              value={stats.total_sessions}
              icon={<FileTextOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="荐购总数"
              value={stats.total_recommendations}
              icon={<BookOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="7天荐购数"
              value={stats.recommendations_7days}
              icon={<BookOutlined style={{ color: '#eb2f96' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 荐购状态统计 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '32px' }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="待处理荐购"
              value={stats.pending_recommendations}
              icon={<ClockCircleOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已批准荐购"
              value={stats.approved_recommendations}
              icon={<CheckOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已拒绝荐购"
              value={stats.rejected_recommendations}
              icon={<CloseOutlined style={{ color: '#f5222d' }} />}
              valueStyle={{ color: '#f5222d' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="平均处理时间"
              value={recStats?.average_processing_time_hours || 0}
              suffix="小时"
              icon={<FileTextOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 荐购概览 */}
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card title="荐购概览" style={{ borderRadius: '8px' }}>
            <Row gutter={[32, 0]}>
              <Col xs={24} sm={12} lg={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#1677ff' }}>
                    {recStats?.total || 0}
                  </div>
                  <div style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
                    总荐购数
                  </div>
                </div>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#faad14' }}>
                    {recStats?.pending || 0}
                  </div>
                  <div style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
                    待处理
                  </div>
                  {recStats?.total > 0 && (
                    <div style={{ color: '#999', fontSize: '12px', marginTop: '4px' }}>
                      ({((recStats.pending / recStats.total) * 100).toFixed(1)}%)
                    </div>
                  )}
                </div>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#52c41a' }}>
                    {recStats?.approved || 0}
                  </div>
                  <div style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
                    已批准
                  </div>
                  {recStats?.total > 0 && (
                    <div style={{ color: '#999', fontSize: '12px', marginTop: '4px' }}>
                      ({((recStats.approved / recStats.total) * 100).toFixed(1)}%)
                    </div>
                  )}
                </div>
              </Col>
              <Col xs={24} sm={12} lg={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#f5222d' }}>
                    {recStats?.rejected || 0}
                  </div>
                  <div style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
                    已拒绝
                  </div>
                  {recStats?.total > 0 && (
                    <div style={{ color: '#999', fontSize: '12px', marginTop: '4px' }}>
                      ({((recStats.rejected / recStats.total) * 100).toFixed(1)}%)
                    </div>
                  )}
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default AdminDashboard;
