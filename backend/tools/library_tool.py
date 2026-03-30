"""
书店库存查询工具 - 使用LLM生成模拟库存数据
"""

import logging
import os
import json
import random
from typing import List, Dict

try:
    from dashscope import Generation
except ImportError:
    Generation = None

logger = logging.getLogger(__name__)


def _generate_mock_inventory(title: str, author: str) -> List[Dict]:
    """
    使用LLM生成书籍库存信息
    
    Args:
        title: 书名
        author: 作者
        
    Returns:
        库存信息列表，每项包含 title, location, shelf_number, stock, price
    """
    if not Generation:
        logger.warning("dashscope 未安装，使用默认模拟数据")
        return _get_default_inventory(title, author)
    
    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("DASHSCOPE_API_KEY 未设置，使用默认模拟数据")
            return _get_default_inventory(title, author)
        
        # 构建提示词
        prompt = f"""请为以下图书生成书店库存信息，以JSON格式返回：

书名：{title}
作者：{author or '未知'}

判断规则：
1. 畅销书（如：活着、三体、红楼梦、平凡的世界、百年孤独等热门书籍）：生成2-3条库存条目
2. 普通书籍：生成1-2条库存条目  
3. 冷门/专业书籍（如：学术专著、冷门技术书等）：生成0-1条库存条目，甚至可能没有库存

每个条目包含：
- title: 书名（使用用户提供的书名）
- author: 作者（使用用户提供的作者）
- location: 书籍所在区域（如：文学区、社科区、少儿区等）
- shelf_number: 架号（如：A-12-3、B-05-1等格式）
- stock: 库存数量（畅销书20-50本，普通书5-20本，冷门书0-5本）
- price: 定价（合理的图书价格，如 39.80、68.00等，保留两位小数）
- pub_info: 出版信息（如：人民文学出版社 2020年版）
- discount: 折扣信息（可选，畅销书较少折扣，冷门书可能有促销折扣，格式如：8.5折、7折、特价等）
- discount_price: 折扣后的价格（可选，如果有折扣则计算折扣价）

请以以下JSON格式返回（只返回JSON，不要其他文字）：
{{
  "inventory": [
    {{
      "title": "书名",
      "author": "作者",
      "location": "区域名称",
      "shelf_number": "架号",
      "stock": 数量,
      "price": 价格,
      "pub_info": "出版信息",
      "discount": "折扣信息或null",
      "discount_price": 折扣后价格或null
    }}
  ]
}}
"""
        
        response = Generation.call(
            api_key=api_key,
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            result_format="message"
        )
        
        if response.status_code == 200:
            content = response.output.choices[0].message.content
            # 提取JSON部分
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(json_str)
            inventory_list = data.get("inventory", [])
            
            # 添加title字段，确保pub_info存在
            for item in inventory_list:
                item["title"] = title
                if not item.get("pub_info"):
                    item["pub_info"] = f"{random.choice(['人民文学出版社', '商务印书馆', '中华书局', '译林出版社', '中信出版社'])} {random.randint(2018, 2024)}年版"
                # 确保折扣字段存在
                if "discount" not in item:
                    item["discount"] = None
                if "discount_price" not in item:
                    item["discount_price"] = None
            
            logger.debug(f"LLM生成库存: {title} -> {len(inventory_list)}条")
            return inventory_list
        else:
            logger.warning(f"LLM调用失败: {response.message}")
            return _get_default_inventory(title, author)
            
    except Exception as e:
        logger.error(f"生成库存信息失败: {str(e)}")
        return _get_default_inventory(title, author)


def _get_default_inventory(title: str, author: str) -> List[Dict]:
    """
    获取默认库存数据（当LLM调用失败时使用）
    """
    # 根据书名简单判断区域
    location = "综合图书区"
    if any(kw in title for kw in ["小说", "文学", "散文", "诗歌", "故事"]):
        location = "文学区"
    elif any(kw in title for kw in ["历史", "哲学", "社会", "心理", "经济", "管理"]):
        location = "社科区"
    elif any(kw in title for kw in ["儿童", "童话", "绘本", "少儿"]):
        location = "少儿区"
    elif any(kw in title for kw in ["科学", "技术", "计算机", "编程", "Python", "数学"]):
        location = "科技区"
    elif any(kw in title for kw in ["教育", "教材", "考试", "学习"]):
        location = "教育区"
    
    # 生成随机但确定性的数据（同一本书返回相同数据）
    seed = sum(ord(c) for c in title) if title else 0
    random.seed(seed)
    
    shelf_row = random.randint(1, 20)
    shelf_col = random.randint(1, 5)
    stock = random.randint(1, 20)
    price = round(random.uniform(29.8, 128.0), 2)
    
    shelf_number = f"{chr(64 + random.randint(1, 8))}-{shelf_row:02d}-{shelf_col}"
    
    publishers = ["人民文学出版社", "商务印书馆", "中华书局", "译林出版社", "中信出版社", "机械工业出版社", "清华大学出版社"]
    pub_info = f"{random.choice(publishers)} {random.randint(2018, 2024)}年版"
    
    # 约30%的书籍有折扣
    has_discount = random.random() < 0.3
    discount = None
    discount_price = None
    if has_discount:
        discount_options = ["8.5折", "8折", "7.5折", "7折", "6.8折", "5折", "特价"]
        discount = random.choice(discount_options)
        if discount != "特价":
            # 解析折扣数字
            discount_num = float(discount.replace("折", "")) / 10
            discount_price = round(price * discount_num, 2)
        else:
            discount_price = round(price * 0.5, 2)
    
    return [{
        "title": title,
        "author": author,
        "location": location,
        "shelf_number": shelf_number,
        "stock": stock,
        "price": price,
        "pub_info": pub_info,
        "discount": discount,
        "discount_price": discount_price
    }]


def search_library_collection(title: str, author: str) -> List[Dict]:
    """
    查询书店库存信息（使用LLM生成）

    Args:
        title: 书名
        author: 作者

    Returns:
        库存信息列表，每项包含 title, location, shelf_number, stock, price
    """
    if not title:
        return []
    
    logger.debug(f"查询库存: {title} - {author or '未知作者'}")
    
    try:
        result = _generate_mock_inventory(title, author)
        logger.debug(f"库存记录: {len(result)}条")
        return result
    except Exception as e:
        logger.error(f"查询库存失败: {str(e)}")
        return []


if __name__ == "__main__":
    print("=== 测试库存查询 ===")
    result = search_library_collection("活着", "余华")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n=== 测试科技类 ===")
    result = search_library_collection("Python编程从入门到实践", "Eric Matthes")
    print(json.dumps(result, ensure_ascii=False, indent=2))
