"""
第六章示例代码2: AgentScope 框架 - 三国狼人杀游戏
基于 AgentScope 2.0 真实 API 实现
"""

import os
import asyncio
from typing import List, Optional
from collections import Counter
from dotenv import load_dotenv

# AgentScope 2.0 标准导入
from agentscope.agent import Agent
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.credential import OpenAICredential
from agentscope.event import EventType

load_dotenv()


def create_model():
    """创建模型客户端"""
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=os.environ["OPENAI_API_KEY"]
        ),
        model=os.environ.get("OPENAI_MODEL", "kimi-k2.6"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )


def create_werewolf_agent(name: str, character: str, model) -> Agent:
    """创建狼人智能体"""
    return Agent(
        name=f"{character}({name})",
        system_prompt=f"""你是{character}，在这场三国狼人杀游戏中扮演狼人。

重要规则：
1. 你只能通过对话和推理参与游戏
2. 不要尝试调用任何外部工具或函数
3. 严格按照要求的JSON格式回复

角色特点：
- 你是狼人阵营，目标是消灭所有好人
- 夜晚可以与其他狼人协商击杀目标
- 白天要隐藏身份，误导好人
- 以{character}的性格说话和行动""",
        model=model,
    )


def create_villager_agent(name: str, character: str, role: str, model) -> Agent:
    """创建好人阵营智能体"""
    role_desc = {
        "预言家": "你是好人阵营，每晚可以查验一名玩家的身份。目标是找出所有狼人。",
        "女巫": "你是好人阵营，拥有解药和毒药。解药可以救人，毒药可以毒杀。",
        "村民": "你是好人阵营，通过推理和投票找出狼人。"
    }
    
    return Agent(
        name=f"{character}({name})",
        system_prompt=f"""你是{character}，在这场三国狼人杀游戏中扮演{role}。

重要规则：
1. 你只能通过对话和推理参与游戏
2. 不要尝试调用任何外部工具或函数
3. 严格按照要求的JSON格式回复

角色特点：
- {role_desc.get(role, '你是好人阵营')}
- 白天要分享信息，但要注意保护自己
- 以{character}的性格说话和行动""",
        model=model,
    )


class ThreeKingdomsWerewolfGame:
    """三国狼人杀游戏"""
    
    def __init__(self, players_config: List[dict], max_discussion_round: int = 3):
        self.max_discussion_round = max_discussion_round
        self.model = create_model()
        self.players: List[Agent] = []
        self.werewolves: List[Agent] = []
        self.alive_players: List[Agent] = []
        self.round = 0
        
        # 创建玩家
        for config in players_config:
            if config["role"] == "狼人":
                player = create_werewolf_agent(config["role"], config["character"], self.model)
                self.werewolves.append(player)
            else:
                player = create_villager_agent(config["role"], config["character"], config["role"], self.model)
            
            self.players.append(player)
        
        self.alive_players = self.players.copy()
    
    async def _get_agent_response(self, agent: Agent, prompt: str) -> str:
        """获取智能体响应"""
        response_parts = []
        async for evt in agent.reply_stream(UserMsg("主持人", prompt)):
            if evt.type == EventType.TEXT_BLOCK_DELTA:
                response_parts.append(evt.delta)
        
        return "".join(response_parts)
    
    async def werewolf_phase(self) -> Optional[Agent]:
        """狼人阶段"""
        if not self.werewolves:
            return None
        
        print("\n【狼人阶段】")
        print("🐺 狼人请睁眼，选择今晚要击杀的目标...")
        
        # 讨论阶段
        alive_names = [p.name for p in self.alive_players]
        print(f"狼人们，请讨论今晚的击杀目标。存活玩家：{alive_names}")
        
        for i in range(self.max_discussion_round):
            print(f"  讨论轮次 {i+1}/{self.max_discussion_round}")
            for wolf in self.werewolves:
                response = await self._get_agent_response(
                    wolf, 
                    f"请分析当前局势并表达你的观点。存活玩家：{alive_names}"
                )
                print(f"  {wolf.name}: {response[:100]}...")
        
        # 投票阶段
        print("请选择击杀目标")
        votes = []
        for wolf in self.werewolves:
            response = await self._get_agent_response(
                wolf,
                f"请选择要击杀的目标。存活玩家：{alive_names}。请回复：目标姓名|理由"
            )
            # 解析响应
            if "|" in response:
                target, reason = response.split("|", 1)
                votes.append(target.strip())
        
        # 统计投票
        if votes:
            vote_count = Counter(votes)
            target_name = vote_count.most_common(1)[0][0]
            
            # 找到目标玩家
            victim = next((p for p in self.alive_players if target_name in p.name), None)
            if victim:
                print(f"🌙 狼人选择了击杀: {victim.name}")
                return victim
        
        return None
    
    async def seer_phase(self):
        """预言家阶段"""
        print("\n【预言家阶段】")
        print("🔮 预言家请睁眼，选择要查验的玩家...")
        
        seer = next((p for p in self.alive_players if "预言家" in p.name), None)
        if seer:
            alive_names = [p.name for p in self.alive_players]
            response = await self._get_agent_response(
                seer,
                f"请选择要查验的玩家。存活玩家：{alive_names}"
            )
            print(f"  {seer.name}查验了: {response}")
    
    async def witch_phase(self, victim: Agent):
        """女巫阶段"""
        print("\n【女巫阶段】")
        print("🧙‍♀️ 女巫请睁眼...")
        
        if victim:
            print(f"今晚{victim.name}被狼人击杀")
        
        witch = next((p for p in self.alive_players if "女巫" in p.name), None)
        if witch:
            response = await self._get_agent_response(
                witch,
                f"请选择你的行动。1.使用解药救{victim.name} 2.使用毒药 3.不行动"
            )
            print(f"  {witch.name}行动: {response}")
    
    async def day_discussion_phase(self):
        """白天讨论阶段"""
        print("\n【白天讨论阶段】")
        print("☀️ 天亮了，请大家睁眼...")
        
        alive_names = [p.name for p in self.alive_players]
        print(f"现在开始自由讨论。存活玩家：{alive_names}")
        
        for player in self.alive_players:
            response = await self._get_agent_response(
                player,
                "请发表你的看法和怀疑对象"
            )
            print(f"  {player.name}: {response[:100]}...")
    
    async def vote_phase(self):
        """投票阶段"""
        print("\n【投票阶段】")
        print("请投票选择要淘汰的玩家")
        
        alive_names = [p.name for p in self.alive_players]
        votes = []
        
        for player in self.alive_players:
            response = await self._get_agent_response(
                player,
                f"请投票选择要淘汰的玩家。存活玩家：{alive_names}。请回复：玩家姓名|理由"
            )
            if "|" in response:
                target, reason = response.split("|", 1)
                votes.append(target.strip())
        
        # 统计投票
        if votes:
            vote_count = Counter(votes)
            target_name = vote_count.most_common(1)[0][0]
            print(f"投票结果：{target_name} 被淘汰")
    
    async def play_round(self):
        """进行一轮游戏"""
        self.round += 1
        print(f"\n{'='*60}")
        print(f"🎮 第{self.round}轮游戏")
        print(f"{'='*60}")
        
        # 夜晚阶段
        print(f"\n🌙 第{self.round}夜降临，天黑请闭眼...")
        victim = await self.werewolf_phase()
        await self.seer_phase()
        await self.witch_phase(victim)
        
        # 白天阶段
        await self.day_discussion_phase()
        await self.vote_phase()
    
    async def run_game(self, max_rounds: int = 5):
        """运行游戏"""
        print("🎮 欢迎来到三国狼人杀！")
        print(f"\n=== 游戏初始化 ===")
        print(f"参与者：{[p.name for p in self.players]}")
        print(f"狼人：{[w.name for w in self.werewolves]}")
        print(f"✅ 游戏设置完成，共{len(self.players)}名玩家")
        
        for i in range(max_rounds):
            await self.play_round()
        
        print(f"\n{'='*60}")
        print("游戏结束！")


async def main():
    """主函数"""
    players_config = [
        {"role": "狼人", "character": "孙权"},
        {"role": "狼人", "character": "周瑜"},
        {"role": "预言家", "character": "曹操"},
        {"role": "村民", "character": "张飞"},
        {"role": "女巫", "character": "司马懿"},
        {"role": "村民", "character": "赵云"},
    ]
    
    game = ThreeKingdomsWerewolfGame(players_config, max_discussion_round=2)
    await game.run_game(max_rounds=2)


if __name__ == "__main__":
    asyncio.run(main())
