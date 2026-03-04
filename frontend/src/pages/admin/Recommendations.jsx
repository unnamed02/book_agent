import { useState, useEffect } from 'react';
import { Table, Button, Select, Spin, message, Modal, Drawer, Tag, Input } from 'antd';
import { CheckOutlined, CloseOutlined, FileTextOutlined } from '@ant-design/icons';
import axios from 'axios';

function AdminRecommendations() {
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [statusFilter, setStatusFilter] = useState(null);
  const [selectedRec, setSelectedRec] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [updating, setUpdating] = useState(false);

  const apiBaseUrl = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : `http://${window.location.hostname}:8001`;

  useEffect(() => {
    fetchRecommendations();
  }, [pagination.current, pagination.pageSize, statusFilter]);

  const fetchRecommendations = async () => {
    try {
      setLoading(true);
      const [recsRes, totalRes] = await Promise.all([
        axios.get(`${apiBaseUrl}/recommendations`, {
          params: {
            page: pagination.current,
            page_size: pagination.pageSize,
            status: statusFilter
          }
        }),
        axios.get(`${apiBaseUrl}/recommendations/total`, {
          params: { status: statusFilter }
        })
      ]);

      setRecommendations(recsRes.data);
      setTotal(totalRes.data.total);
    } catch (error) {
      console.error('获取荐购列表失败:', error);
      message.error('获取荐购列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (id, newStatus) => {
    try {
      setUpdating(true);
      await axios.patch(`${apiBaseUrl}/recommendations/${id}`, {
        status: newStatus
      });
      message.success('状态更新成功');
      fetchRecommendations();
      setDrawerVisible(false);
    } catch (error) {
      console.error('更新状态失败:', error);
      message.error('更新状态失败');
    } finally {
      setUpdating(false);
    }
  };

  const handleStatusChange = (id, newStatus) => {
    Modal.confirm({
      title: '确认更新',
      content: `确定要将荐购状态更改为"${
        newStatus === 'approved' ? '已批准' : newStatus === 'rejected' ? '已拒绝' : '待处理'
      }"吗？`,
      okText: '确认',
      cancelText: '取消',
      onOk() {
        handleUpdateStatus(id, newStatus);
      }
    });
  };

  const getStatusTag = (status) => {
    const statusConfig = {
      pending: { color: 'orange', text: '待处理' },
      approved: { color: 'green', text: '已批准' },
      rejected: { color: 'red', text: '已拒绝' }
    };
    const config = statusConfig[status] || { color: 'gray', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const columns = [
    {
      title: '书名',
      dataIndex: 'book_title',
      key: 'book_title',
      width: 200,
      ellipsis: true
    },
    {
      title: '作者',
      dataIndex: 'author',
      key: 'author',
      width: 150,
      ellipsis: true
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => getStatusTag(status)
    },
    {
      title: '提交时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => new Date(date).toLocaleString('zh-CN'),
      sorter: (a, b) => new Date(a.created_at) - new Date(b.created_at)
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<FileTextOutlined />}
          onClick={() => {
            setSelectedRec(record);
            setDrawerVisible(true);
          }}
        >
          详情
        </Button>
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
        <Select
          placeholder="按状态过滤"
          style={{ width: '200px' }}
          allowClear
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { label: '待处理', value: 'pending' },
            { label: '已批准', value: 'approved' },
            { label: '已拒绝', value: 'rejected' }
          ]}
        />
        <Button onClick={() => {
          setPagination({ current: 1, pageSize: 20 });
          fetchRecommendations();
        }}>
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={recommendations}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: total,
            onChange: (page, pageSize) => {
              setPagination({ current: page, pageSize });
            }
          }}
          scroll={{ x: 1000 }}
        />
      </Spin>

      <Drawer
        title="荐购详情"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={500}
      >
        {selectedRec && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>书名</div>
              <div style={{ fontSize: '16px', fontWeight: 'bold' }}>{selectedRec.book_title}</div>
            </div>

            {selectedRec.author && (
              <div>
                <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>作者</div>
                <div>{selectedRec.author}</div>
              </div>
            )}

            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>用户ID</div>
              <div style={{ wordBreak: 'break-all', fontSize: '12px', fontFamily: 'monospace' }}>
                {selectedRec.user_id}
              </div>
            </div>

            {selectedRec.contact && (
              <div>
                <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>联系方式</div>
                <div>{selectedRec.contact}</div>
              </div>
            )}

            {selectedRec.notes && (
              <div>
                <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>备注</div>
                <div style={{
                  background: '#fafafa',
                  padding: '8px 12px',
                  borderRadius: '4px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {selectedRec.notes}
                </div>
              </div>
            )}

            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>提交时间</div>
              <div>{new Date(selectedRec.created_at).toLocaleString('zh-CN')}</div>
            </div>

            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>状态</div>
              <div style={{ marginBottom: '12px' }}>
                {getStatusTag(selectedRec.status)}
              </div>
            </div>

            {selectedRec.status === 'pending' && (
              <div style={{
                display: 'flex',
                gap: '8px',
                paddingTop: '12px',
                borderTop: '1px solid #f0f0f0'
              }}>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  loading={updating}
                  onClick={() => handleStatusChange(selectedRec.id, 'approved')}
                  block
                >
                  批准
                </Button>
                <Button
                  danger
                  icon={<CloseOutlined />}
                  loading={updating}
                  onClick={() => handleStatusChange(selectedRec.id, 'rejected')}
                  block
                >
                  拒绝
                </Button>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}

export default AdminRecommendations;
