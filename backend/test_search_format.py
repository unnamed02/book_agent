"""测试搜索来源数据格式"""
import os
import json
from dashscope import Generation

# 测试查询
test_query = "《活着》这本书讲什么"

response = Generation.call(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model="qwen-max",
    messages=[{"role": "user", "content": test_query}],
    enable_search=True,
    search_options={
        "enable_source": True,
    },
    result_format="message"
)

if response.status_code == 200:
    print("Response output keys:", dir(response.output))
    print("\nSearch info:", response.output.get("search_info", {}))
    
    # 尝试获取 choices
    if hasattr(response.output, 'choices'):
        print("\nChoices:", response.output.choices)
        if response.output.choices:
            first_choice = response.output.choices[0]
            print("\nFirst choice keys:", dir(first_choice))
            print("\nFirst choice message keys:", dir(first_choice.message))
else:
    print("Error:", response.message)
