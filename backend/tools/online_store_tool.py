"""
网店在售查询工具 - 使用LLM生成网店在售数据
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


def _generate_online_stores(title: str, author: str) -> List[Dict]:
    """
    使用LLM生成网店在售信息
    
    Args:
        title: 书名
        author: 作者
        
    Returns:
        网店在售列表，每项包含 source, pub_info, price, link
    """
    if not Generation:
        logger.warning("dashscope 未安装，使用默认模拟数据")
        return _get_default_online_stores(title, author)
    
    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("DASHSCOPE_API_KEY 未设置，使用默认模拟数据")
            return _get_default_online_stores(title, author)
        
        # 构建提示词
        prompt = f"""请为以下图书生成网店在售信息，以JSON格式返回：

书名：{title}
作者：{author or '未知'}

判断规则（网店比实体店更全）：
1. 畅销书（如：活着、三体、红楼梦、平凡的世界、百年孤独等热门书籍）：生成3条（满）网店在售条目
2. 普通书籍：生成2-3条网店在售条目  
3. 冷门/专业书籍（如：学术专著、冷门技术书等）：生成1-2条网店在售条目（网店通常也能找到）

来源包括：鲨鱼书店、陕西新华天猫网店等。
每个条目包含：
- title: 书名（使用用户提供的书名）
- author: 作者（使用用户提供的作者）
- source: 网店名称（如：鲨鱼书店、陕西新华天猫网店）
- pub_info: 出版信息（如：人民文学出版社 2020年版）
- price: 售价（合理的图书价格，如 39.80、68.00等，保留两位小数）
- link: 商品链接（生成一个合理的URL格式，如 https://www.sharks.com/book/xxx 或 https://sxhx.tmall.com/item/xxx）
- discount: 折扣信息（可选，网店折扣通常比实体店多，格式如：8.5折、7折、特价等）
- discount_price: 折扣后的价格（可选，如果有折扣则计算折扣价）
- original_price: 原价（可选，如果有折扣则显示原价）

请以以下JSON格式返回（只返回JSON，不要其他文字）：
{{
  "stores": [
    {{
      "title": "书名",
      "author": "作者",
      "source": "网店名称",
      "pub_info": "出版信息",
      "price": 价格,
      "link": "商品链接",
      "discount": "折扣信息或null",
      "discount_price": 折扣后价格或null,
      "original_price": 原价或null
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
            stores_list = data.get("stores", [])
            
            # 添加title字段
            for item in stores_list:
                item["title"] = title
                # 确保折扣字段存在
                if "discount" not in item:
                    item["discount"] = None
                if "discount_price" not in item:
                    item["discount_price"] = None
                if "original_price" not in item:
                    item["original_price"] = None
            
            logger.debug(f"LLM生成网店信息: {title} -> {len(stores_list)}条")
            return stores_list
        else:
            logger.warning(f"LLM调用失败: {response.message}")
            return _get_default_online_stores(title, author)
            
    except Exception as e:
        logger.error(f"生成网店信息失败: {str(e)}")
        return _get_default_online_stores(title, author)


def _get_default_online_stores(title: str, author: str) -> List[Dict]:
    """
    获取默认网店数据（当LLM调用失败时使用）
    """
    # 生成随机但确定性的数据（同一本书返回相同数据）
    seed = sum(ord(c) for c in title) if title else 0
    random.seed(seed)
    
    stores = ["鲨鱼书店", "陕西新华天猫网店"]
    publishers = ["人民文学出版社", "商务印书馆", "中华书局", "译林出版社", "中信出版社"]
    
    result = []
    for store in stores:
        pub_info = f"{random.choice(publishers)} {random.randint(2018, 2024)}年版"
        price = round(random.uniform(29.8, 128.0), 2)
        
        # 约30%的书籍有折扣
        has_discount = random.random() < 0.3
        discount = None
        discount_price = None
        original_price = None
        if has_discount:
            discount_options = ["8.5折", "8折", "7.5折", "7折", "6.8折", "5折", "特价"]
            discount = random.choice(discount_options)
            original_price = price
            if discount != "特价":
                discount_num = float(discount.replace("折", "")) / 10
                discount_price = round(price * discount_num, 2)
            else:
                discount_price = round(price * 0.5, 2)
        
        if store == "鲨鱼书店":
            link = f"https://www.sharksbook.com/item/{random.randint(10000000, 99999999)}"
        else:
            link = f"https://sxhx.tmall.com/item/{random.randint(1000000000, 9999999999)}.html"
        
        result.append({
            "title": title,
            "author": author,
            "source": store,
            "pub_info": pub_info,
            "price": price,
            "link": link,
            "discount": discount,
            "discount_price": discount_price,
            "original_price": original_price
        })
    
    return result


def search_online_stores(title: str, author: str) -> List[Dict]:
    """
    查询网店在售信息（使用LLM生成）

    Args:
        title: 书名
        author: 作者

    Returns:
        网店在售列表，每项包含 source, pub_info, price, link
    """
    if not title:
        return []
    
    logger.debug(f"查询网店在售: {title} - {author or '未知作者'}")
    
    try:
        result = _generate_online_stores(title, author)
        logger.debug(f"网店记录: {len(result)}条")
        return result
    except Exception as e:
        logger.error(f"查询网店在售失败: {str(e)}")
        return []


if __name__ == "__main__":
    print("=== 测试网店在售查询 ===")
    result = search_online_stores("活着", "余华")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n=== 测试科技类 ===")
    result = search_online_stores("Python编程从入门到实践", "Eric Matthes")
    print(json.dumps(result, ensure_ascii=False, indent=2))
