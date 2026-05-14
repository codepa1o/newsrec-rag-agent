# NewsRec-RAG Agent

面向新闻推荐系统的 Agentic RAG 个性化推荐与实验平台。项目结合 MINDlarge 抽样数据、用户行为建模、多策略推荐、Learning-to-Rank、离线评估、本地资料库 RAG、多 Agent 协作、FastAPI 后端和 Streamlit 演示界面，适合作为简历中的第二个 Agent 项目。

当前默认使用本地 sample 数据，包含新闻、用户行为和演示账号。没有配置 DashScope 时，系统会使用本地 hashing embedding、fallback 文本生成和纯 Python LTR 模型，保证项目可以离线演示。

## 核心亮点

- 新闻推荐系统：用户画像、多路召回、重排序、多样性过滤、冷启动推荐、兴趣漂移分析。
- Learning-to-Rank：基于 MIND 行为数据构造点击样本，训练轻量 LTR 模型，支持特征贡献解释。
- 多策略实验平台：热门 baseline、类别偏好、向量语义、反馈增强、Agentic RAG、LTR、Hybrid LTR + RAG 对比。
- 离线评估：HitRate@K、MRR@K、NDCG@K、AUC、覆盖率、多样性、新颖性、校准度。
- 实验追踪：评估和消融实验写入 SQLite，可查看历史实验和指标详情。
- 本地资料库 RAG：Markdown/TXT/PDF 上传、PDF OCR fallback、文档切分、混合检索、引用来源、幻觉控制。
- 多 Agent 协作：Planner、Router、UserProfiler、Retriever、NewsAnalyst、Reranker、Experiment、Answer、CitationVerifier。
- 工程化：FastAPI、Streamlit、SQLite、ChromaDB-ready、DashScope-ready、Docker、GitHub Actions、pytest。

## 架构图

```text
Streamlit UI
   |
   v
FastAPI API
   |
   +-- RecommendationExperimentService
   |     +-- hot / category / vector / feedback / agentic_rag
   |     +-- ltr_rerank / hybrid_ltr_rag
   |     +-- HitRate / MRR / NDCG / AUC / Coverage / Diversity
   |
   +-- LearningToRankService
   |     +-- MIND behavior samples
   |     +-- feature extraction
   |     +-- pure Python logistic LTR model
   |     +-- recommendation explanation
   |
   +-- NewsRecommender
   |     +-- vector recall
   |     +-- category recall
   |     +-- hot recall
   |     +-- rerank + diversity filter
   |
   +-- RAGService
   |     +-- dense retrieval
   |     +-- keyword retrieval
   |     +-- citation verifier
   |     +-- answer evaluation
   |
   +-- MultiAgentResearchWorkflow
         +-- PlannerAgent
         +-- RouterAgent
         +-- RetrieverAgent
         +-- RerankAgent
         +-- ExperimentAgent
         +-- CitationVerifierAgent
```

## 推荐模型训练流程

```text
MIND behaviors.tsv
   -> impressions: clicked / unclicked
   -> build user profile
   -> extract features
      category_match
      keyword_overlap
      semantic_similarity
      popularity
      freshness
      recent_interest
      feedback_weight
      document_topic_match
   -> train LTR model
   -> save data/models/ltr_model.json
   -> ltr_rerank / hybrid_ltr_rag recommendation
   -> feature contribution explanation
```

## 快速启动

```powershell
cd E:\pythonlearning\code\agent_learning\newsrec-rag-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run_dev.ps1
```

打开：

```text
Streamlit UI: http://127.0.0.1:8501
API Docs:     http://127.0.0.1:8000/docs
```

默认演示账号：

```text
用户名：U100
密码：demo123456
```

## 页面功能

- `系统仪表盘`：新闻数、用户数、资料库、RAG 查询、行为闭环指标。
- `推荐`：个性化新闻流。
- `新闻详情`：站内详情、收藏、反馈、AI 摘要、问答、本地资料解读、排序解释入口。
- `推荐策略对比`：对比热门、类别、向量、反馈增强、Agentic RAG、LTR、Hybrid LTR + RAG。
- `实验评估`：多策略 HitRate、MRR、NDCG、AUC、覆盖率、多样性、新颖性、校准度。
- `模型训练`：一键训练 LTR，查看样本数、模型状态和特征列表。
- `实验追踪`：查看历史实验记录和指标详情。
- `消融分析`：比较去掉语义、反馈、RAG 特征、多样性后的推荐变化。
- `推荐解释`：展示 LTR 特征值、权重和贡献。
- `本地资料库`：上传、解析、切分、索引本地资料。
- `资料库问答`：混合检索、引用来源、答案评估。
- `Agent 运行观测`：展示多 Agent trace。

## 主要 API

```text
GET  /metrics/overview

POST /models/ltr/train
GET  /models/ltr/status
POST /recommend/ltr
GET  /me/recommend/explain/{news_id}

POST /recommend/compare
POST /recommend/cold-start
POST /evaluate/strategies
POST /evaluate/ablation
GET  /experiments
GET  /experiments/{experiment_id}

GET  /me/interest-drift
POST /me/daily-briefing
POST /me/rag/hybrid-query
POST /me/agent/trace

GET  /articles/{news_id}/event-cluster
GET  /articles/{news_id}/viewpoints
```

完整示例见：

```text
docs/api_examples.http
```

## DashScope / Qwen

复制 `.env.example` 为 `.env`，按需配置：

```text
DASHSCOPE_API_KEY=your-key
USE_DASHSCOPE=true
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v4
RERANK_MODEL=qwen3-rerank
AI_CACHE_ENABLED=true
AI_TIMEOUT_SECONDS=30
```

未配置 Key 时，系统仍可运行本地 fallback。

## 数据与模型

默认数据路径：

```text
data/sample/news.tsv
data/sample/behaviors.tsv
```

LTR 模型路径：

```text
data/models/ltr_model.json
```

从 MINDlarge 重新抽样：

```powershell
python scripts/build_mind_sample.py --source E:\postgraduatelearning\MTP-Rec\datasets\MINDlarge\MINDlarge_train --output data/sample --max-behaviors 1200 --max-extra-news 800
```

## Docker

```powershell
docker compose up --build
```

访问：

```text
API: http://127.0.0.1:8000
UI:  http://127.0.0.1:8501
```

## 测试

```powershell
pytest
```

当前覆盖：

- 推荐结果结构、反馈闭环、收藏和浏览历史。
- 文档上传、切分、RAG 问答、引用校验。
- 多策略推荐对比、离线评估、实验追踪。
- LTR 训练、推荐、特征解释、消融实验。
- 兴趣漂移、事件聚类、AI 日报、多 Agent trace。

## 简历描述

构建面向新闻推荐系统的 Agentic RAG 推荐实验平台，基于 MINDlarge 抽样数据实现用户画像、多路召回、重排序、多样性控制、冷启动推荐和 HitRate/MRR/NDCG/AUC 离线评估；实现基于用户行为数据的 Learning-to-Rank 模型，支持特征工程、模型训练、LTR 重排、Hybrid LTR + RAG 推荐和特征贡献解释；设计本地资料库 RAG，支持 Markdown/TXT/PDF 上传、OCR fallback、混合检索、引用溯源、幻觉控制和答案评估；使用 LangGraph 编排 Planner、Router、Retriever、Reranker、Experiment、CitationVerifier 等多 Agent 工作流，并通过 FastAPI + Streamlit 提供可观测演示界面、实验追踪和消融分析看板。
