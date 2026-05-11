# 智能新闻推荐 RAG Agent

面向新闻推荐系统的 Agentic RAG 个性化推荐平台。项目结合 MIND 新闻推荐数据集思路、用户行为建模、语义检索、重排序、RAG 解释、登录注册、收藏浏览历史和 DashScope/Qwen AI 能力，适合作为简历中的第二个 Agent 项目。

没有下载 MIND 或配置 DashScope 时，项目会自动使用内置 sample 数据、本地 hashing embedding 和 AI fallback，方便先完整跑通。

## Features

- 登录注册：SQLite 存储用户、会话、反馈、收藏、浏览历史。
- 个性化推荐：基于历史点击、收藏、浏览、喜欢、屏蔽类别构建兴趣画像。
- 多路召回：语义检索、类别召回、热度召回。
- 推荐解释：规则解释 + DashScope/Qwen AI 推荐解释 fallback。
- 新闻详情页：点击标题进入站内详情页，可查看推荐理由、相关新闻和原文链接。
- AI 新闻能力：新闻摘要、新闻问答、用户画像总结。
- 智能推荐助手：用自然语言描述需求，返回相关新闻。
- 评估指标：HitRate@K、MRR@K、NDCG@K。
- 中文 UI：登录/注册居中展示，使用 `ui/assets/boki.png` 作为全屏背景图。
- 工程栈：FastAPI、Streamlit、LangGraph、LangChain、ChromaDB-ready、DashScope-ready。

## Quick Start

```powershell
cd E:\pythonlearning\code\agent_learning\newsrec-rag-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

一键启动：

```powershell
.\run_dev.ps1
```

启动后打开：

```text
Streamlit UI: http://127.0.0.1:8501
API Docs:     http://127.0.0.1:8000/docs
```

默认演示账号：

```text
用户名：U100
密码：demo123456
```

数据库默认位置：

```text
data/newsrec.db
```

## Main APIs

```text
GET  /health
POST /auth/register
POST /auth/login
POST /auth/logout

GET  /me
GET  /me/profile
GET  /me/profile/summary
GET  /me/recommend?top_k=10
GET  /me/articles/{news_id}
POST /me/articles/{news_id}/view
POST /me/articles/{news_id}/favorite
POST /me/articles/{news_id}/summary
POST /me/articles/{news_id}/ask
GET  /me/favorites
GET  /me/history
POST /me/feedback
POST /me/agent/recommend

GET  /users/U100/profile
GET  /recommend/U100?top_k=10
GET  /articles/N1006
POST /evaluate
```

## DashScope / Qwen

复制 `.env.example` 为 `.env`，配置：

```text
DASHSCOPE_API_KEY=your-key
USE_DASHSCOPE=true
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v4
RERANK_MODEL=qwen3-rerank
AI_CACHE_ENABLED=true
AI_TIMEOUT_SECONDS=30
```

未配置 Key 时，AI 摘要、新闻问答、画像总结会返回 fallback，项目仍可演示。

## MIND Dataset

默认路径：

```text
data/mind/MINDsmall_train/news.tsv
data/mind/MINDsmall_train/behaviors.tsv
```

下载并解压 MINDsmall 后放到上述目录即可。验证解析：

```powershell
python scripts/ingest_mind.py --news data/mind/MINDsmall_train/news.tsv --behaviors data/mind/MINDsmall_train/behaviors.tsv
```

## Tests

```powershell
pytest
```

## Resume Description

构建面向新闻推荐场景的 Agentic RAG 个性化推荐系统，基于 MIND 数据集思路实现用户兴趣建模、多路召回、语义检索、重排序、可解释推荐、新闻详情页、收藏浏览历史和 AI 新闻问答；使用 LangGraph 编排推荐流程，FastAPI 提供推荐与认证服务，Streamlit 构建交互式中文推荐面板，并通过 HitRate@K、MRR@K、NDCG@K 评估推荐效果。
