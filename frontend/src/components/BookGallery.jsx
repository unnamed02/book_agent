import { useState, useEffect, useRef } from 'react';
import { Button, Space } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import BookCard from './BookCard';

const BookGallery = ({ books, onRecommend }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const containerRef = useRef(null);

  const goToPrev = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : books.length - 1));
  };

  const goToNext = () => {
    setCurrentIndex((prev) => (prev < books.length - 1 ? prev + 1 : 0));
  };

  // 计算每个卡片的位置和样式
  const getCardStyle = (index) => {
    const diff = index - currentIndex;
    const absDistance = Math.abs(diff);
    const isActive = index === currentIndex;
    
    // 只显示当前卡片及其左右的卡片，其他的隐藏
    if (absDistance > 2) {
      return {
        opacity: 0,
        pointerEvents: 'none',
        transform: `translateX(${diff * 260}px) scale(0.7)`,
      };
    }
    
    const translateX = isActive ? 0 : diff * 310; // 中间卡片不动，两侧偏移
    const scale = isActive ? 1.25 : Math.max(0.35, 1.25 - absDistance * 0.6);
    const opacity = isActive ? 1 : Math.max(0.5, 1 - absDistance * 0.25);
    const zIndex = isActive ? 100 : 100 - absDistance * 10;

    return {
      transform: `translateX(${translateX}px) scale(${scale})`,
      opacity,
      zIndex,
      transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
    };
  };

  if (!books || books.length === 0) {
    return null;
  }

  return (
    <div style={{ width: '100%' }}>
      {/* 导航按钮 */}
      {books.length > 1 && (
        <div style={{ 
          position: 'relative',
          height: 32,
          marginBottom: 12,
          padding: '0 60px'
        }}>
          {/* 左侧箭头 */}
          <Button 
            type="text"
            icon={<LeftOutlined />} 
            onClick={goToPrev} 
            size="small"
            style={{ position: 'absolute', left: 60, top: 26 }}
          />
          
          {/* 中间页码 */}
          <span style={{ 
            position: 'absolute', 
            left: '50%', 
            top: 30,
            transform: 'translateX(-50%)',
            fontSize: 12, 
            color: '#666' 
          }}>
            {currentIndex + 1} / {books.length}
          </span>
          
          {/* 右侧箭头 */}
          <Button 
            type="text"
            icon={<RightOutlined />} 
            onClick={goToNext} 
            size="small"
            style={{ position: 'absolute', right: 60, top: 26 }}
          />
        </div>
      )}

      {/* 轮播容器 */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          height: 720,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          overflow: 'hidden',
        }}
      >
        {books.map((book, idx) => (
          <div
            key={idx}
            onClick={() => setCurrentIndex(idx)}
            style={{
              position: 'absolute',
              width: 300,
              cursor: 'pointer',
              borderRadius: 12,
              overflow: 'visible',
              ...getCardStyle(idx),
            }}
          >
            <BookCard books={[book]} onRecommend={onRecommend} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default BookGallery;
