"""
上下文构建器示例
演示 ContextBuilder 的基本使用
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import math

from dotenv import load_dotenv
load_dotenv()

@dataclass
class ContextPacket:
    """候选信息包
    Attributes:
        content: 信息内容
        timestamp: 时间戳
        token_count: Token 数量
        relevance_score: 相关性分数(0.0-1.0)
        metadata: 可选的元数据
    """
    content: str
    timestamp: datetime
    token_count: int
    relevance_score: float = 0.5
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.metadata is None:
            self.metadata = {}
        # 确保相关性分数在有效范围内
        self.relevance_score = max(0.0, min(1.0, self.relevance_score))


@dataclass
class ContextConfig:
    """上下文构建配置
    Attributes:
        max_tokens: 最大 token 数量
        reserve_ratio: 为系统指令预留的比例(0.0-1.0)
        min_relevance: 最低相关性阈值
        enable_compression: 是否启用压缩
        recency_weight: 新近性权重(0.0-1.0)
        relevance_weight: 相关性权重(0.0-1.0)
    """
    max_tokens: int = 3000
    reserve_ratio: float = 0.2
    min_relevance: float = 0.1
    enable_compression: bool = True
    recency_weight: float = 0.3
    relevance_weight: float = 0.7

    def __post_init__(self):
        """验证配置参数"""
        assert 0.0 <= self.reserve_ratio <= 1.0, "reserve_ratio 必须在 [0, 1] 范围内"
        assert 0.0 <= self.min_relevance <= 1.0, "min_relevance 必须在 [0, 1] 范围内"
        assert abs(self.recency_weight + self.relevance_weight - 1.0) < 1e-6, \
            "recency_weight + relevance_weight 必须等于 1.0"


class SimpleContextBuilder:
    """简化版上下文构建器，演示 GSSC 流水线"""
    
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
    
    def _count_tokens(self, text: str) -> int:
        """估算文本的 token 数量"""
        # 简单估算: 中文 1 字符 ≈ 1 token, 英文 1 单词 ≈ 1.3 tokens
        chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
        english_words = len([w for w in text.split() if w])
        return int(chinese_chars + english_words * 1.3)
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """计算内容与查询的相关性（Jaccard 相似度）"""
        content_words = set(content.lower().split())
        query_words = set(query.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = content_words & query_words
        union = content_words | query_words
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_recency(self, timestamp: datetime) -> float:
        """计算时间近因性分数（指数衰减）"""
        age_hours = (datetime.now() - timestamp).total_seconds() / 3600
        
        # 指数衰减: 24小时内保持高分，之后逐渐衰减
        decay_factor = 0.1
        recency_score = math.exp(-decay_factor * age_hours / 24)
        
        return max(0.1, min(1.0, recency_score))
    
    def gather(self, user_query: str, conversation_history: List[str] = None) -> List[ContextPacket]:
        """Gather 阶段: 多源信息汇集"""
        packets = []
        
        # 1. 添加对话历史
        if conversation_history:
            for i, msg in enumerate(conversation_history[-5:]):  # 保留最近5条
                packets.append(ContextPacket(
                    content=msg,
                    timestamp=datetime.now(),
                    token_count=self._count_tokens(msg),
                    relevance_score=0.6,
                    metadata={"type": "conversation_history", "index": i}
                ))
        
        print(f"[Gather] 汇集了 {len(packets)} 个候选信息包")
        return packets
    
    def select(self, packets: List[ContextPacket], user_query: str, available_tokens: int) -> List[ContextPacket]:
        """Select 阶段: 智能信息选择"""
        # 计算综合分数
        scored_packets = []
        for packet in packets:
            # 计算相关性分数
            if packet.relevance_score == 0.5:  # 默认值，需要重新计算
                relevance = self._calculate_relevance(packet.content, user_query)
                packet.relevance_score = relevance
            
            # 计算新近性分数
            recency = self._calculate_recency(packet.timestamp)
            
            # 综合分数 = 相关性权重 × 相关性 + 新近性权重 × 新近性
            combined_score = (
                self.config.relevance_weight * packet.relevance_score +
                self.config.recency_weight * recency
            )
            
            # 过滤低于最小相关性阈值的信息
            if packet.relevance_score >= self.config.min_relevance:
                scored_packets.append((combined_score, packet))
        
        # 按分数降序排序
        scored_packets.sort(key=lambda x: x[0], reverse=True)
        
        # 贪心选择: 按分数从高到低填充，直到达到 token 上限
        selected = []
        current_tokens = 0
        
        for score, packet in scored_packets:
            if current_tokens + packet.token_count <= available_tokens:
                selected.append(packet)
                current_tokens += packet.token_count
            else:
                break
        
        print(f"[Select] 选择了 {len(selected)} 个信息包，共 {current_tokens} tokens")
        return selected
    
    def structure(self, selected_packets: List[ContextPacket], user_query: str) -> str:
        """Structure 阶段: 结构化输出"""
        # 按类型分组
        conversation = []
        other = []
        
        for packet in selected_packets:
            packet_type = packet.metadata.get("type", "general")
            if packet_type == "conversation_history":
                conversation.append(packet.content)
            else:
                other.append(packet.content)
        
        # 构建结构化模板
        sections = []
        
        # [Task]
        sections.append(f"[Task]\n{user_query}")
        
        # [Context]
        if conversation:
            sections.append("[Context]\n" + "\n".join(conversation))
        
        # [Output]
        sections.append("[Output]\n请基于以上信息，提供准确、有据的回答。")
        
        return "\n\n".join(sections)
    
    def compress(self, context: str, max_tokens: int) -> str:
        """Compress 阶段: 兜底压缩"""
        current_tokens = self._count_tokens(context)
        
        if current_tokens <= max_tokens:
            return context  # 无需压缩
        
        print(f"[Compress] 上下文超限({current_tokens} > {max_tokens})，执行压缩")
        
        # 分区压缩: 保持结构完整性
        sections = context.split("\n\n")
        compressed_sections = []
        current_total = 0
        
        for section in sections:
            section_tokens = self._count_tokens(section)
            
            if current_total + section_tokens <= max_tokens:
                # 完整保留
                compressed_sections.append(section)
                current_total += section_tokens
            else:
                # 部分保留
                remaining_tokens = max_tokens - current_total
                if remaining_tokens > 50:  # 至少保留 50 tokens
                    # 简单截断
                    char_per_token = len(section) / section_tokens if section_tokens > 0 else 4
                    max_chars = int(remaining_tokens * char_per_token)
                    truncated = section[:max_chars]
                    compressed_sections.append(truncated + "\n[... 内容已压缩 ...]")
                break
        
        compressed_context = "\n\n".join(compressed_sections)
        final_tokens = self._count_tokens(compressed_context)
        print(f"[Compress] 压缩完成: {current_tokens} -> {final_tokens} tokens")
        
        return compressed_context
    
    def build(self, user_query: str, conversation_history: List[str] = None) -> str:
        """构建上下文（完整 GSSC 流水线）"""
        # 1. Gather
        packets = self.gather(user_query, conversation_history)
        
        # 2. Select
        available_tokens = int(self.config.max_tokens * (1 - self.config.reserve_ratio))
        selected = self.select(packets, user_query, available_tokens)
        
        # 3. Structure
        structured = self.structure(selected, user_query)
        
        # 4. Compress
        compressed = self.compress(structured, self.config.max_tokens)
        
        return compressed


def main():
    """演示上下文构建器的使用"""
    print("=" * 80)
    print("上下文构建器 (ContextBuilder) 示例")
    print("=" * 80)
    
    # 1. 创建配置
    config = ContextConfig(
        max_tokens=500,
        reserve_ratio=0.2,
        min_relevance=0.1,
        recency_weight=0.3,
        relevance_weight=0.7
    )
    
    # 2. 创建构建器
    builder = SimpleContextBuilder(config)
    
    # 3. 模拟对话历史
    conversation_history = [
        "用户: 我正在开发一个数据分析工具",
        "助手: 很好！数据分析工具通常需要处理大量数据。您计划使用什么技术栈？",
        "用户: 我打算使用Python和Pandas，已经完成了CSV读取模块",
        "助手: 不错的选择！Pandas在数据处理方面非常强大。接下来您可能需要考虑数据清洗和转换。",
        "用户: 如何优化Pandas的内存占用？"
    ]
    
    # 4. 构建上下文
    user_query = "如何优化Pandas的内存占用？"
    context = builder.build(user_query, conversation_history)
    
    # 5. 输出结果
    print("\n" + "=" * 80)
    print("构建的上下文:")
    print("=" * 80)
    print(context)
    print("=" * 80)
    
    # 6. 统计信息
    print(f"\n统计信息:")
    print(f"- 最大 token 预算: {config.max_tokens}")
    print(f"- 保留比例: {config.reserve_ratio}")
    print(f"- 实际使用 tokens: {builder._count_tokens(context)}")
    print(f"- 相关性权重: {config.relevance_weight}")
    print(f"- 新近性权重: {config.recency_weight}")


if __name__ == "__main__":
    main()