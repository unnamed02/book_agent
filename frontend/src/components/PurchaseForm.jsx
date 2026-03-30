import { useState } from 'react';
import { Card, Form, Input, Button, message as antMessage, Space } from 'antd';
import { ShoppingOutlined, CheckCircleOutlined } from '@ant-design/icons';



const PurchaseForm = ({ title = '', author = '', onSubmit }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const initialValues = {
    title: title || '',
    author: author || '',
    note: '',
    contact: ''
  };

  const handleSubmit = async (values) => {
    if (submitting || submitted) return;

    setSubmitting(true);
    try {
      const apiBaseUrl = window.location.hostname === 'localhost'
        ? 'http://localhost:8000'
        : `http://${window.location.hostname}:8000`;

      const response = await fetch(`${apiBaseUrl}/purchase/recommend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: values.title,
          author: values.author,
          note: values.note,
          contact: values.contact
        }),
      });

      if (response.ok) {
        setSubmitted(true);
        antMessage.success('荐购申请已提交，感谢您的推荐！');
        if (onSubmit) {
          onSubmit(values);
        }
      } else {
        throw new Error('提交失败');
      }
    } catch (error) {
      console.error('提交荐购失败:', error);
      antMessage.error('提交失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <Card
        
        style={{
          width: 375,
          background: '#fff',
          borderRadius: 12,
          border: '1px solid #e8e8e8'
        }}
      >
        <Space orientation="vertical" align="center" style={{ width: '100%', padding: '20px 0' }}>
          <CheckCircleOutlined style={{ fontSize: 48, color: '#1677ff' }} />
          <div style={{ fontSize: 16, fontWeight: 600, color: '#1677ff', marginBottom: 8 }}>感谢您的荐购！</div>
          <div style={{ fontSize: 13, color: '#666' }}>我们会尽快处理您的荐购申请</div>
        </Space>
      </Card>
    );
  }

  return (
    <Card
      
      style={{
        width: 375,
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #e8e8e8',
        overflow: 'hidden'
      }}
      title={
        <Space>
          <ShoppingOutlined style={{ color: '#1677ff' }} />
          <span style={{ color: '#262626', fontSize: 13 }}>荐购图书</span>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={handleSubmit}
      >
        <Form.Item
          label="书名"
          name="title"
          rules={[{ required: true, message: '请输入书名' }]}
        >
          <Input
            placeholder="请输入书名"
            disabled={submitting}
          />
        </Form.Item>

        <Form.Item
          label="作者"
          name="author"
        >
          <Input
            placeholder="请输入作者"
            disabled={submitting}
          />
        </Form.Item>

        <Form.Item
          label="备注（选填）"
          name="note"
        >
          <Input.TextArea
            placeholder="指定ISBN、出版社、版本等，方便我们确定最优质版本"
            rows={3}
            maxLength={200}
            showCount
            disabled={submitting}
          />
        </Form.Item>

        <Form.Item
          label="电话号码（选填）"
          name="contact"
        >
          <Input
            placeholder="填写后，该书上架将通过短信告知您"
            disabled={submitting}
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            htmlType="submit"
            loading={submitting}
            block
            size="large"
          >
            {submitting ? '提交中...' : '提交荐购'}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default PurchaseForm;
