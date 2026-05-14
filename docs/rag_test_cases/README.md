# RAG 功能测试用例

这个目录提供一组可以直接上传到 Streamlit `本地资料库` 页面的测试资料，用来验证 NewsRec-RAG Agent V3 的本地资料库 RAG、多 Agent 协作和新闻资料解读功能。

## 测试资料

- `ai_recommendation_governance.md`：测试推荐透明度、可解释推荐、反馈闭环、幻觉控制和评估指标。
- `local_rag_policy_notes.txt`：测试 TXT 解析、引用来源、扫描 PDF/OCR 设计和多 Agent 角色。
- `news_recommendation_research.md`：测试新闻推荐系统研究方向、多路召回、重排序和 RAG 推荐解释。

## 手动测试流程

1. 启动项目：

```powershell
cd E:\pythonlearning\code\agent_learning\newsrec-rag-agent
.\run_dev.ps1
```

2. 打开 Streamlit：

```text
http://127.0.0.1:8501
```

3. 使用演示账号登录：

```text
用户名：U100
密码：demo123456
```

4. 进入 `本地资料库` 页面，依次上传本目录下的三个测试文件。

5. 进入 `资料库问答` 页面，使用下面的问题测试。

## 推荐测试问题

### 召回与引用来源

问题：

```text
新闻推荐系统为什么需要推荐透明度？
```

预期：

- 回答应提到用户理解推荐依据、减少误解。
- 引用来源应包含 `ai_recommendation_governance.md`。
- 引用片段应来自 `推荐透明度` 或 `可解释推荐` 附近。

### 文档切分与 metadata

问题：

```text
Markdown 和 PDF 文档应该如何切分？
```

预期：

- 回答应提到 Markdown 按标题层级切分，TXT/PDF 按段落切分。
- 引用来源应包含 `local_rag_policy_notes.txt`。
- citation 中应展示文件名和 chunk 信息。

### 幻觉控制

问题：

```text
资料中有没有提到 2028 年某个虚构法规的处罚金额是多少？
```

预期：

- 回答应明确资料不足。
- `missing_evidence` 应为 `true` 或回答中出现“没有找到足够依据”。
- 不应该编造具体法规和处罚金额。

### 答案评估

问题：

```text
RAG 问答模块应该如何评估回答质量？
```

预期：

- 回答应提到 faithfulness、answer relevance、citation coverage。
- 结果里应展示 `evaluation` 字段。

### 新闻推荐结合 RAG

问题：

```text
结合我的资料库，解释为什么 AI 监管新闻适合推荐给我。
```

预期：

- 回答应同时涉及 AI 治理、透明度、合规、推荐解释。
- 多 Agent 助手中应展示 RouterAgent、RetrieverAgent、RerankAgent、AnswerAgent、VerifierAgent。

## 新闻详情页测试

1. 进入 `推荐` 页面。
2. 点击任意 AI、科技或推荐系统相关新闻标题。
3. 在 `新闻详情` 页点击 `资料解读`。

预期：

- 出现 `本地资料解读` 区域。
- 展示回答、可信度、引用来源和多 Agent 运行轨迹。
- 如果当前新闻与资料库关系较弱，应返回保守解释，而不是编造。

## API 冒烟测试

也可以运行脚本：

```powershell
python scripts/rag_smoke_test.py
```

脚本会自动登录、上传测试资料、执行 RAG 问答、新闻资料解读和多 Agent 聊天。
