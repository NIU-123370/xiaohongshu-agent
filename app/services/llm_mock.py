"""
Mock LLM 服务模块
模拟 LLM API 调用，用于开发和测试
"""
import asyncio
from typing import List


class MockLLMService:
    """Mock LLM 服务类"""
    
    @staticmethod
    async def plan_topics(topic_direction: str) -> List[str]:
        """
        根据主题方向生成候选选题
        
        Args:
            topic_direction: 用户输入的主题方向
            
        Returns:
            生成的选题列表
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.5)
        
        # 返回固定的选题列表
        base_topics = [
            "LangGraph入门：构建你的第一个AI工作流",
            "AI Agent实战：从零搭建智能助手",
            "Python高并发编程：asyncio深度解析",
            "RAG系统设计：让AI更懂你的业务",
            "Prompt Engineering最佳实践指南"
        ]
        
        # 根据主题方向微调（模拟个性化）
        if topic_direction:
            return [f"{topic} - {topic_direction}方向" for topic in base_topics[:3]] + base_topics[3:]
        
        return base_topics
    
    @staticmethod
    async def write_draft(
        topic: str, 
        feedback: str = "",
        revision_count: int = 0
    ) -> str:
        """
        根据选题生成文章草稿
        
        Args:
            topic: 选中的选题
            feedback: 用户的修改意见（用于修订）
            revision_count: 当前修订次数
            
        Returns:
            生成的文章内容
        """
        # 模拟 API 延迟
        await asyncio.sleep(1.0)
        
        # 根据是否有反馈意见生成不同内容
        revision_prefix = ""
        if feedback and revision_count > 0:
            revision_prefix = f"""【根据意见已修改】
            
修改说明：针对"{feedback}"的意见，本次已进行第 {revision_count} 次修订。

---

"""
        
        article = f"""{revision_prefix}# {topic}

## 引言

在当今快速发展的技术领域，{topic} 已经成为开发者必须掌握的核心技能之一。本文将深入探讨这一主题，帮助读者全面理解其核心概念和实践应用。

## 核心概念

### 什么是 {topic.split('：')[0] if '：' in topic else topic}？

{topic.split('：')[0] if '：' in topic else topic} 是一种创新的技术范式，它改变了我们构建和部署智能应用的方式。通过合理运用这项技术，开发者可以显著提升开发效率和应用性能。

### 关键特性

1. **高效性**：通过优化的算法和架构设计，实现高性能处理
2. **可扩展性**：支持横向和纵向扩展，适应不同规模的应用场景
3. **易用性**：提供简洁的 API 和丰富的文档支持
4. **可靠性**：内置错误处理和重试机制，确保系统稳定运行

## 实战案例

让我们通过一个具体的例子来理解如何在实际项目中应用这些概念：

```python
# 示例代码
from example_lib import ExampleClass

def main():
    instance = ExampleClass()
    result = instance.process()
    print(f"处理结果: {{result}}")

if __name__ == "__main__":
    main()
```

## 最佳实践

在实际开发中，我们建议遵循以下最佳实践：

- 始终进行充分的测试
- 注重代码的可读性和可维护性
- 合理使用设计模式
- 持续学习和更新知识体系

## 总结

通过本文的学习，相信读者已经对 {topic} 有了更深入的理解。技术的发展日新月异，保持学习的热情是每个开发者成长的关键。

---

*本文由 AI 内容助手生成，仅供参考学习使用。*
"""
        
        return article
    
    @staticmethod
    async def extract_visual_points(article_content: str) -> List[str]:
        """
        从文章中提取适合配图的要点
        
        Args:
            article_content: 文章内容
            
        Returns:
            图片文案要点列表
        """
        # 模拟 API 延迟
        await asyncio.sleep(0.3)
        
        # 返回固定的视觉要点
        visual_points = [
            "技术架构流程图：展示核心组件之间的交互关系",
            "代码示例截图：突出关键实现细节",
            "对比图表：新旧方案的性能对比",
            "思维导图：知识点总结和梳理",
            "封面图：吸引眼球的主题配图"
        ]
        
        return visual_points


# 创建单例实例
mock_llm_service = MockLLMService()
