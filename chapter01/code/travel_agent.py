"""
第一章示例代码：智能旅行助手
基于 Thought-Action-Observation 范式
支持从.env文件加载配置（需安装python-dotenv）
"""

import os
import re
import requests
from openai import OpenAI

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ 已从.env文件加载配置")
except ImportError:
    print("⚠️  未安装python-dotenv，将使用环境变量或直接配置")
    print("   安装命令: pip install python-dotenv")

AGENT_SYSTEM_PROMPT = """
你是一个智能旅行助手。你的任务是分析用户的请求，并使用可用工具一步步地解决问题。

# 可用工具:
- `get_weather(city: str)`: 查询指定城市的实时天气。
- `get_attraction(city: str, weather: str)`: 根据城市和天气搜索推荐的旅游景点。

# 输出格式要求:
你的每次回复必须严格遵循以下格式，包含一对Thought和Action：

Thought: [你的思考过程和下一步计划]
Action: [你要执行的具体行动]

Action的格式必须是以下之一：
1. 调用工具：function_name(arg_name="arg_value")
2. 结束任务：Finish[最终答案]

# 重要提示:
- 每次只输出一对Thought-Action
- Action必须在同一行，不要换行
- 当收集到足够信息可以回答用户问题时，必须使用 Action: Finish[最终答案] 格式结束

请开始吧！
"""


def get_weather(city: str) -> str:
    """通过调用 wttr.in API 查询真实的天气信息。"""
    url = f"https://wttr.in/{city}?format=j1"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        current_condition = data['current_condition'][0]
        weather_desc = current_condition['weatherDesc'][0]['value']
        temp_c = current_condition['temp_C']
        
        return f"{city}当前天气：{weather_desc}，气温{temp_c}摄氏度"
        
    except requests.exceptions.RequestException as e:
        return f"错误：查询天气时遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        return f"错误：解析天气数据失败，可能是城市名称无效 - {e}"


def get_attraction(city: str, weather: str) -> str:
    """根据城市和天气，搜索推荐的旅游景点（模拟版本）。"""
    attractions_db = {
        "北京": {
            "晴天": ["颐和园", "故宫", "长城", "天坛"],
            "多云": ["颐和园", "北海公园", "798艺术区"],
            "雨天": ["国家博物馆", "故宫博物院", "798艺术区"],
        },
        "上海": {
            "晴天": ["外滩", "东方明珠", "迪士尼乐园", "豫园"],
            "多云": ["外滩", "南京路步行街", "田子坊"],
            "雨天": ["上海博物馆", "中华艺术宫", "上海科技馆"],
        },
        "杭州": {
            "晴天": ["西湖", "雷峰塔", "灵隐寺", "西溪湿地"],
            "多云": ["西湖", "断桥残雪", "千岛湖"],
            "雨天": ["宋城", "浙江省博物馆", "杭州乐园"],
        },
    }
    
    weather_simplified = "晴天" if "晴" in weather or "Sunny" in weather else \
                         "雨天" if "雨" in weather or "Rain" in weather else "多云"
    
    if city in attractions_db and weather_simplified in attractions_db[city]:
        spots = attractions_db[city][weather_simplified]
        return f"根据{weather}天气，推荐您游览：{', '.join(spots)}"
    else:
        return f"推荐{city}的知名景点：博物馆、公园、历史古迹等（天气：{weather}）"


available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}


class OpenAICompatibleClient:
    """用于调用任何兼容OpenAI接口的LLM服务的客户端。"""
    
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        """调用LLM API来生成回应。"""
        print("正在调用大语言模型...")
        try:
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ]
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            answer = response.choices[0].message.content
            print("✅ 大语言模型响应成功。")
            return answer
        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return "错误：调用语言模型服务时出错。"


class TravelAgent:
    """智能旅行助手Agent，实现Thought-Action-Observation循环。"""
    
    def __init__(self, llm_client: OpenAICompatibleClient, max_iterations: int = 5):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.prompt_history = []
        
    def run(self, user_prompt: str) -> str:
        """运行Agent主循环。"""
        print(f"\n用户输入: {user_prompt}")
        print("="*60)
        self.prompt_history = [f"用户请求: {user_prompt}"]
        
        for i in range(self.max_iterations):
            print(f"\n--- 循环 {i+1} ---\n")
            
            full_prompt = "\n".join(self.prompt_history)
            llm_output = self.llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
            
            # 截断多余的Thought-Action
            match = re.search(
                r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)', 
                llm_output, 
                re.DOTALL
            )
            if match:
                truncated = match.group(1).strip()
                if truncated != llm_output.strip():
                    llm_output = truncated
                    print("已截断多余的 Thought-Action 对")
            
            print(f"模型输出:\n{llm_output}\n")
            self.prompt_history.append(llm_output)
            
            # 解析Action
            action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
            if not action_match:
                observation = "错误: 未能解析到 Action 字段"
                self._add_observation(observation)
                continue
                
            action_str = action_match.group(1).strip()
            
            # 检查是否结束
            if action_str.startswith("Finish"):
                # 修复：支持多行内容，添加 re.DOTALL 标志
                match = re.match(r"Finish\[(.*)\]", action_str, re.DOTALL)
                if match:
                    final_answer = match.group(1)
                else:
                    # 如果格式不匹配，提取 Finish 后的内容
                    final_answer = action_str[6:].strip("[]")  # 去掉 "Finish" 和括号
                
                print(f"\n{'='*60}")
                print(f"✅ 任务完成！")
                print(f"{'='*60}")
                print(f"最终答案:\n{final_answer}")
                return final_answer
            
            # 执行工具调用
            try:
                tool_name = re.search(r"(\w+)\(", action_str).group(1)
                args_str = re.search(r"\((.*)\)", action_str).group(1)
                kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))
                
                if tool_name in available_tools:
                    observation = available_tools[tool_name](**kwargs)
                else:
                    observation = f"错误：未定义的工具 '{tool_name}'"
                    
            except Exception as e:
                observation = f"错误：解析或执行Action失败 - {e}"
            
            self._add_observation(observation)
        
        return "达到最大循环次数，任务未完成"
    
    def _add_observation(self, observation: str):
        """添加观察结果到历史记录。"""
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "="*40)
        self.prompt_history.append(observation_str)


def check_config():
    """检查配置是否完整。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("OPENAI_MODEL")
    
    if not api_key or api_key == "your_api_key_here":
        return False, "OPENAI_API_KEY 未配置"
    if not base_url:
        return False, "OPENAI_BASE_URL 未配置"
    if not model:
        return False, "OPENAI_MODEL 未配置"
    
    return True, None


def demo_mode():
    """演示模式：无需LLM，模拟Agent执行流程。"""
    print("="*60)
    print("演示模式（无需LLM）：智能旅行助手")
    print("="*60)
    
    user_input = input("\n请输入城市名称（如：北京、上海、杭州）：") or "北京"
    
    print(f"\n用户请求: 查询{user_input}天气并推荐景点\n")
    
    print("\n--- 循环 1 ---")
    print("Thought: 用户想了解天气，我需要先调用天气查询工具")
    print(f'Action: get_weather(city="{user_input}")')
    weather_result = get_weather(user_input)
    print(f"Observation: {weather_result}")
    
    print("\n--- 循环 2 ---")
    print(f"Thought: 已获取天气信息，现在可以根据天气推荐景点")
    print(f'Action: get_attraction(city="{user_input}", weather="{weather_result}")')
    attraction_result = get_attraction(user_input, weather_result)
    print(f"Observation: {attraction_result}")
    
    print("\n--- 循环 3 ---")
    print("Thought: 已收集足够信息，可以生成最终答案")
    print("Action: Finish[完整的旅行推荐]")
    print(f"\n{'='*60}")
    print(f"最终答案:\n{weather_result}\n{attraction_result}")
    print(f"{'='*60}")


def llm_mode():
    """LLM模式：使用真实LLM驱动Agent。"""
    print("="*60)
    print("LLM模式：智能旅行助手")
    print("="*60)
    
    # 检查配置
    is_configured, error_msg = check_config()
    if not is_configured:
        print(f"\n⚠️  配置错误: {error_msg}")
        print("请确保 .env 文件存在且配置正确，或设置环境变量。")
        print("\n将使用演示模式...\n")
        return demo_mode()
    
    # 创建客户端和Agent
    llm = OpenAICompatibleClient(
        model=os.environ.get("OPENAI_MODEL"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL")
    )
    
    agent = TravelAgent(llm_client=llm, max_iterations=5)
    
    # 运行
    user_prompt = input("\n请输入您的旅行请求：") or "你好，请帮我查询一下今天北京的天气，然后根据天气推荐一个合适的旅游景点。"
    agent.run(user_prompt)


if __name__ == "__main__":
    # 检查是否有配置，有则使用LLM模式，否则使用演示模式
    is_configured, _ = check_config()
    
    if is_configured:
        print("✅ 检测到API配置，使用LLM模式")
        llm_mode()
    else:
        print("⚠️  未检测到API配置，使用演示模式")
        print("提示：创建.env文件并填入API信息可启用LLM模式\n")
        demo_mode()
