from __future__ import annotations

from app.models import Article, Behavior, Impression


def sample_articles() -> dict[str, Article]:
    articles = [
        Article(
            news_id="N1001",
            category="科技",
            subcategory="人工智能",
            title="通义千问模型提升企业搜索中的多语言推理能力",
            abstract="阿里云发布更强的语言模型能力，可用于检索增强、复杂推理和智能体工作流。",
            popularity=42,
        ),
        Article(
            news_id="N1002",
            category="科技",
            subcategory="云计算",
            title="向量数据库成为 RAG 系统的标准基础设施",
            abstract="越来越多工程团队使用向量检索、元数据过滤和重排序构建可靠的 AI 应用。",
            popularity=37,
        ),
        Article(
            news_id="N1003",
            category="财经",
            subcategory="市场",
            title="芯片股带动科技板块上涨，全球市场情绪回暖",
            abstract="投资者持续关注半导体需求、云计算支出以及 AI 基础设施收入。",
            popularity=35,
        ),
        Article(
            news_id="N1004",
            category="体育",
            subcategory="篮球",
            title="年轻后卫季后赛砍下生涯新高，带队逆转取胜",
            abstract="球队在第四节调整防守策略，最终完成一场关键胜利。",
            popularity=28,
        ),
        Article(
            news_id="N1005",
            category="健康",
            subcategory="研究",
            title="研究人员关注睡眠习惯与长期认知健康的关系",
            abstract="一项多年研究显示，规律睡眠可能与更好的记忆力和注意力有关。",
            popularity=24,
        ),
        Article(
            news_id="N1006",
            category="科技",
            subcategory="推荐系统",
            title="新闻平台测试可解释推荐模型",
            abstract="个性化新闻流正在结合用户历史、语义检索和多样性约束，提升推荐质量。",
            popularity=44,
        ),
        Article(
            news_id="N1007",
            category="国际",
            subcategory="政策",
            title="多国讨论生成式 AI 透明度规则",
            abstract="政策制定者围绕内容披露、安全评估和负责任部署展开讨论。",
            popularity=32,
        ),
        Article(
            news_id="N1008",
            category="文娱",
            subcategory="影视",
            title="流媒体平台加码互动叙事内容",
            abstract="影视公司开始尝试观众选择、个性化预告片和基于推荐的内容发现。",
            popularity=26,
        ),
    ]
    return {article.news_id: article for article in articles}


def sample_behaviors() -> list[Behavior]:
    return [
        Behavior(
            impression_id="1",
            user_id="U100",
            time="05/10/2026 08:00:00 AM",
            history=("N1001", "N1002"),
            impressions=(
                Impression("N1006", True),
                Impression("N1003", False),
                Impression("N1004", False),
            ),
        ),
        Behavior(
            impression_id="2",
            user_id="U200",
            time="05/10/2026 09:00:00 AM",
            history=("N1004",),
            impressions=(
                Impression("N1003", False),
                Impression("N1005", True),
                Impression("N1008", False),
            ),
        ),
    ]
