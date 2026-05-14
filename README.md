# 智能新闻推荐 RAG Agent

面向新闻推荐系统的 Agentic RAG 个性化推荐平台。项目结合 MIND 新闻推荐数据集思路、用户行为建模、多路召回、重排序、可解释推荐、登录注册、收藏历史、DashScope/Qwen AI 能力，并在 V3 新增 **本地资料库 RAG + 多 Agent 协作**。

项目默认使用从 MINDlarge 抽取的本地 sample 数据，当前包含约 1.4 万条新闻和 1200 条用户行为；没有配置 DashScope 时，系统会自动使用本地 hashing embedding 和 AI fallback，方便完整演示。

## 核心功能

- 登录注册：SQLite 存储用户、会话、反馈、收藏、浏览历史。
- 个性化推荐：结合历史点击、收藏、浏览、喜欢、屏蔽类别构建兴趣画像。
- 新闻详情页：点击标题进入站内详情页，查看推荐理由、相关新闻、AI 摘要和新闻问答。
- 本地资料库 RAG：支持上传 Markdown、TXT、PDF，解析、切分、向量索引并在回答中引用来源。
- 扫描版 PDF 支持：普通 PDF 使用 PyMuPDF 提取文本，扫描版 PDF 尝试使用 rapidocr-onnxruntime OCR。
- RAG 问答：包含召回、启发式重排、引用来源、证据不足保护、答案评估。
- 新闻资料解读：在新闻详情页结合用户上传资料解释新闻与资料库的关系。
- 多 Agent 助手：Router、Retriever、Reranker、Answer、Verifier 协作，展示运行轨迹。
- 评估看板：HitRate@K、MRR@K、NDCG@K。
- 工程栈：FastAPI、Streamlit、LangGraph、LangChain、ChromaDB-ready、DashScope-ready、SQLite、pytest。

## 快速启动

```powershell
cd E:\pythonlearning\code\agent_learning\newsrec-rag-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

启动后端和前端：

```powershell
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

## V3 使用方式

1. 登录后进入 `本地资料库` 页面。
2. 上传 `.md`、`.txt` 或 `.pdf` 文件。
3. 进入 `资料库问答` 页面，围绕上传资料提问。
4. 在 `新闻详情` 页面点击 `资料解读`，查看这篇新闻和本地资料的关联。
5. 在 `多 Agent 助手` 输入自然语言需求，例如：

```text
结合我上传的资料，推荐几篇 AI 监管相关的新闻
```

回答会展示引用来源、可信度、答案评估和多 Agent 运行轨迹。

## 主要 API

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
POST /me/articles/{news_id}/grounded-analysis
GET  /me/favorites
GET  /me/history
POST /me/feedback

POST /me/documents/upload
GET  /me/documents
GET  /me/documents/{document_id}
DELETE /me/documents/{document_id}
POST /me/documents/{document_id}/reindex
POST /me/rag/query
POST /me/agent/recommend
POST /me/agent/chat

GET  /users/U100/profile
GET  /recommend/U100?top_k=10
GET  /articles/N1006
POST /evaluate
```

## 本地资料库 RAG 设计

- Markdown：按标题层级切分，保留标题路径。
- TXT / PDF：先按段落切分，超长段落再递归切分。
- 默认 chunk size：约 1000 字符。
- 默认 overlap：160 字符。
- 每个 chunk 保留：document_id、filename、page、heading_path、chunk_index、snippet。
- 向量索引：默认本地内存索引；设置 `USE_CHROMA=true` 后写入 ChromaDB。
- 幻觉控制：没有足够证据时返回“本地资料中没有找到足够依据”，不会强行编造。

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

未配置 Key 时，AI 摘要、新闻问答、资料库问答会返回本地 fallback，项目仍可演示。

## 数据与配置

```text
data/newsrec.db        SQLite 数据库
data/sample            从 MINDlarge 抽取的演示新闻和行为数据
data/uploads           上传资料
data/chroma            ChromaDB 持久化目录
data/mind              MIND 数据目录
```

默认数据路径：

```text
data/sample/news.tsv
data/sample/behaviors.tsv
```

如果你想从自己的 MINDlarge 重新抽样：

```powershell
python scripts/build_mind_sample.py --source E:\postgraduatelearning\MTP-Rec\datasets\MINDlarge\MINDlarge_train --output data/sample --max-behaviors 1200 --max-extra-news 800
```

验证 MIND 解析：

```powershell
python scripts/ingest_mind.py --news data/sample/news.tsv --behaviors data/sample/behaviors.tsv
```

## 测试

```powershell
pytest
```

当前测试覆盖：

- MIND 解析
- 推荐结果结构
- 登录、收藏、浏览历史、反馈
- 文档上传、Markdown 切分、RAG 问答
- 新闻资料解读
- 多 Agent workflow
- HitRate@K、MRR@K、NDCG@K

## 简历描述

构建面向新闻推荐系统的 Agentic RAG 个性化推荐平台，基于 MIND 数据集思路实现用户兴趣建模、多路召回、语义检索、重排序、可解释推荐、新闻详情页和离线评估；扩展本地资料库 RAG，支持 Markdown/TXT/PDF 上传、文档切分、向量索引、引用溯源、幻觉控制和答案评估；使用 LangGraph 编排 Router、Retriever、Reranker、Answer、Verifier 多 Agent 协作流程，FastAPI 提供推荐与资料库服务，Streamlit 构建中文交互式演示界面。
