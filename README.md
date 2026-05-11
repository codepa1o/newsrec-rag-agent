# 智能新闻推荐 RAG Agent

面向新闻推荐系统的 Agentic RAG 个性化推荐平台。项目使用 MIND 新闻推荐数据集思路，结合用户历史点击、语义检索、重排序、解释生成和反馈闭环，展示一个可写进简历的第二个 Agent 项目。

没有下载 MIND 或配置 DashScope 时，项目会自动使用内置 sample 数据和本地 hashing embedding，方便先完整跑通。

## Features

- MIND `news.tsv`、`behaviors.tsv` 解析
- 用户兴趣画像：类别偏好、关键词、近期点击、屏蔽类别
- 多路召回：语义检索、类别召回、热度召回
- 重排序：语义分、类别偏好、关键词重合、热度
- RAG 风格解释：推荐理由和证据片段
- ReAct 工具函数：画像、搜索、推荐、解释、反馈、评估
- LangGraph workflow：画像加载、召回、重排、多样性、解释节点
- FastAPI 后端和 Streamlit 前端
- 登录注册：SQLite 存储用户、会话和反馈数据
- 离线指标：HitRate@K、MRR@K、NDCG@K

## Quick Start

```powershell
cd E:\pythonlearning\code\agent_learning\newsrec-rag-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

启动后端：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
streamlit run ui/streamlit_app.py
```

或者直接运行一键启动脚本：

```powershell
.\run_dev.ps1
```

脚本会自动使用 `.venv`，分别启动 FastAPI 和 Streamlit，并把日志写入 `logs/`。

默认演示账号：

```text
用户名：U100
密码：demo123456
```

数据库默认位置：

```text
data/newsrec.db
```

常用接口：

```text
GET  /health
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /me
GET  /me/profile
GET  /me/recommend?top_k=10
POST /me/feedback
GET  /users/U100/profile
GET  /recommend/U100?top_k=10
GET  /articles/N1006
POST /feedback
POST /evaluate
```

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

## DashScope

复制 `.env.example` 为 `.env`，配置：

```text
DASHSCOPE_API_KEY=your-key
USE_DASHSCOPE=true
EMBEDDING_MODEL=text-embedding-v4
RERANK_MODEL=qwen3-rerank
```

当前实现默认使用本地 hashing embedding，保证无 key 可运行；DashScope embedding/rerank 已预留适配层，可进一步切换到在线模型。

## Tests

```powershell
pytest
```

## Resume Description

构建面向新闻推荐场景的 Agentic RAG 个性化推荐系统，基于 MIND 数据集实现用户兴趣建模、多路召回、语义检索、重排序与可解释推荐；使用 LangGraph 编排画像构建、候选召回、重排序、解释生成等流程，使用 FastAPI 提供推荐服务，Streamlit 构建交互式推荐面板，并通过 HitRate@K、MRR@K、NDCG@K 评估推荐效果。
