# NewsRec-RAG Agent UI 设计说明

## 设计目标

V4 UI 的目标不是做营销页，而是把系统包装成一个可演示的新闻推荐实验平台：

- 信息层级清晰：登录后优先看到系统仪表盘，再进入推荐、实验、RAG 和 Agent 观测。
- 视觉简洁高级：浅色中性背景、白色半透明面板、深青色与酒红色作为功能强调色。
- 交互稳定：页面切换使用轻量淡入上移动画，按钮 hover 有轻微位移和阴影，避免干扰阅读。
- 简历展示友好：每个核心能力都有独立页面，方便演示“推荐系统 + RAG + 多 Agent + 工程化”。

## 视觉规格

```text
背景         boki.png + 高透明浅色蒙层
主文字       #20272c
次级文字     #687278
主强调色     #18777f
辅助强调色   #9f3f5f
警示/金色    #c58b32
面板背景     rgba(255,255,255,0.82)
圆角         8px
阴影         0 18px 54px rgba(34,42,46,0.13)
字体策略     Streamlit 默认系统字体，保持现代可读
```

## 页面结构

```text
登录页
  - 居中标题区
  - 登录 / 注册 Tab
  - 默认演示账号提示

登录后
  - 左侧导航 Sidebar
  - 顶部 Hero：页面英文标签 + 中文标题 + 当前页面说明
  - 主内容区：
      系统仪表盘：指标卡 + 类别分布 + 能力总览
      推荐：兴趣画像 + AI 画像总结 + 新闻流
      新闻详情：站内内容 + 摘要 + 问答 + 资料解读
      推荐策略对比：多策略结果分组
      实验评估：HitRate / MRR / NDCG 表格
      本地资料库：上传、文档列表、切片查看
      资料库问答：混合检索、引用、答案评估
      Agent 运行观测：最终回答 + Trace + 引用 + 新闻
```

## 动画实现

Streamlit 无原生路由动画，因此通过 CSS 对主容器和页面块做轻量动效：

```css
.block-container {
  animation: pageEnter 360ms ease-out both;
}

@keyframes pageEnter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.page-shell {
  animation: softRise 300ms ease-out both;
}
```

按钮 hover 使用 `transform: translateY(-1px)` 和轻阴影，形成可感知但不夸张的交互反馈。

## Figma 式低保真设计稿

```text
┌────────────────────────────────────────────────────────────┐
│ Sidebar          │  Hero                                   │
│ NewsRec-RAG      │  [Overview] 系统仪表盘                  │
│ - 系统仪表盘     │  查看数据规模、RAG 查询、Agent 状态...   │
│ - 推荐           │                                         │
│ - 新闻详情       │  ┌────────┐ ┌────────┐ ┌────────┐       │
│ - 推荐策略对比   │  │新闻规模│ │用户数  │ │RAG查询 │       │
│ - 实验评估       │  └────────┘ └────────┘ └────────┘       │
│ - 本地资料库     │                                         │
│ - Agent 观测     │  ┌────────────────┐ ┌────────────────┐ │
│                  │  │新闻类别分布    │ │系统能力总览    │ │
│                  │  └────────────────┘ └────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

## 可迁移 React 组件示例

项目当前使用 Streamlit，但下面的组件可作为未来 React/Vue 重构时的基础样式参考。

```tsx
type ArticleCardProps = {
  title: string;
  category: string;
  score?: number;
  abstract?: string;
  reason?: string;
  onOpen: () => void;
};

export function ArticleCard(props: ArticleCardProps) {
  return (
    <article className="article-card">
      <div className="meta-row">
        <span className="pill teal">{props.category}</span>
        {props.score !== undefined && <span className="pill accent">分数 {props.score.toFixed(3)}</span>}
      </div>
      <h3>{props.title}</h3>
      {props.abstract && <p>{props.abstract}</p>}
      {props.reason && <div className="reason-box">{props.reason}</div>}
      <button onClick={props.onOpen}>查看详情</button>
    </article>
  );
}
```

```css
.article-card {
  border: 1px solid rgba(42, 52, 57, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 12px 34px rgba(34, 42, 46, 0.09);
  padding: 16px;
}

.pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 760;
}

.pill.teal {
  background: rgba(24, 119, 127, 0.1);
  color: #17686f;
}

.pill.accent {
  background: rgba(159, 63, 95, 0.1);
  color: #82324f;
}
```
