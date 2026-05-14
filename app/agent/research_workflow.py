from __future__ import annotations

from time import perf_counter
from typing import Any, Literal, TypedDict


Intent = Literal["news_recommendation", "document_qa", "article_analysis", "evaluation", "daily_briefing"]


class ResearchAgentState(TypedDict, total=False):
    user_id: str
    query: str
    top_k: int
    intent: Intent
    plan: list[str]
    news_items: list[dict[str, Any]]
    rag_result: dict[str, Any]
    evaluation_result: dict[str, Any]
    profile_summary: dict[str, Any]
    answer: str
    workflow_trace: list[dict[str, Any]]


class MultiAgentResearchWorkflow:
    """Observable deterministic multi-agent workflow with LangGraph compatibility."""

    def __init__(self, container) -> None:
        self.container = container
        self.graph = self._build_graph()

    def run(self, user_id: str, query: str, top_k: int = 5) -> ResearchAgentState:
        state: ResearchAgentState = {"user_id": user_id, "query": query, "top_k": top_k, "workflow_trace": []}
        if self.graph is None:
            for node in [
                self._planner_agent,
                self._router_agent,
                self._user_profiler_agent,
                self._retriever_agent,
                self._news_analyst_agent,
                self._rerank_agent,
                self._experiment_agent,
                self._answer_agent,
                self._citation_verifier_agent,
            ]:
                state = node(state)
            return state
        return self.graph.invoke(state)

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:  # pragma: no cover
            return None

        graph = StateGraph(ResearchAgentState)
        graph.add_node("PlannerAgent", self._planner_agent)
        graph.add_node("RouterAgent", self._router_agent)
        graph.add_node("UserProfilerAgent", self._user_profiler_agent)
        graph.add_node("RetrieverAgent", self._retriever_agent)
        graph.add_node("NewsAnalystAgent", self._news_analyst_agent)
        graph.add_node("RerankAgent", self._rerank_agent)
        graph.add_node("ExperimentAgent", self._experiment_agent)
        graph.add_node("AnswerAgent", self._answer_agent)
        graph.add_node("CitationVerifierAgent", self._citation_verifier_agent)
        graph.set_entry_point("PlannerAgent")
        graph.add_edge("PlannerAgent", "RouterAgent")
        graph.add_edge("RouterAgent", "UserProfilerAgent")
        graph.add_edge("UserProfilerAgent", "RetrieverAgent")
        graph.add_edge("RetrieverAgent", "NewsAnalystAgent")
        graph.add_edge("NewsAnalystAgent", "RerankAgent")
        graph.add_edge("RerankAgent", "ExperimentAgent")
        graph.add_edge("ExperimentAgent", "AnswerAgent")
        graph.add_edge("AnswerAgent", "CitationVerifierAgent")
        graph.add_edge("CitationVerifierAgent", END)
        return graph.compile()

    def _planner_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        query = state["query"]
        plan = ["识别用户意图", "读取用户画像", "检索新闻或资料", "生成回答", "校验引用与风险"]
        if any(word in query for word in ("评估", "指标", "对比", "实验")):
            plan.insert(3, "运行推荐策略评估")
        state["plan"] = plan
        add_trace(state, "PlannerAgent", {"query": query}, "plan_request", f"拆解为 {len(plan)} 个步骤", {"plan": plan})
        return state

    def _router_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        query = state["query"]
        if any(word in query for word in ("日报", "简报", "今日")):
            intent: Intent = "daily_briefing"
        elif any(word in query for word in ("资料", "文档", "报告", "论文", "引用", "依据")):
            intent = "document_qa"
        elif any(word in query for word in ("评估", "指标", "HitRate", "MRR", "NDCG", "实验", "对比")):
            intent = "evaluation"
        else:
            intent = "news_recommendation"
        state["intent"] = intent
        add_trace(state, "RouterAgent", {"query": query}, "intent_router", f"识别意图：{intent}")
        return state

    def _user_profiler_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        profile = self.container.profile_service.build_profile(state["user_id"]).to_dict()
        state["profile_summary"] = profile
        add_trace(
            state,
            "UserProfilerAgent",
            {"user_id": state["user_id"]},
            "profile_service.build_profile",
            f"偏好类别 {len(profile.get('preferred_categories', []))} 个，关键词 {len(profile.get('keywords', []))} 个",
            profile,
        )
        return state

    def _retriever_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        intent = state["intent"]
        top_k = state.get("top_k", 5)
        query = state["query"]
        if intent == "document_qa":
            state["rag_result"] = self.container.rag_service.hybrid_query(state["user_id"], query, top_k=top_k)
        elif intent == "daily_briefing":
            briefing = self.container.news_intelligence.daily_briefing(state["user_id"], top_k=top_k)
            state["news_items"] = briefing["items"]
            state["answer"] = briefing["briefing"]
        elif intent == "evaluation":
            state["evaluation_result"] = self.container.experiment_service.evaluate_strategies(k_values=[5, 10, top_k])
        else:
            state["news_items"] = [item.to_dict() for item in self.container.recommender.search(query, top_k=top_k)]
            if any(word in query for word in ("结合", "资料", "依据", "RAG")):
                state["rag_result"] = self.container.rag_service.hybrid_query(state["user_id"], query, top_k=3)
        add_trace(state, "RetrieverAgent", {"intent": intent, "top_k": top_k}, "hybrid_retrieval", "完成新闻库/资料库检索")
        return state

    def _news_analyst_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        items = state.get("news_items", [])
        categories = {}
        for item in items:
            categories[item.get("category", "unknown")] = categories.get(item.get("category", "unknown"), 0) + 1
        add_trace(state, "NewsAnalystAgent", {"items": len(items)}, "category_distribution", "分析候选新闻主题与类别", categories)
        return state

    def _rerank_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        items = state.get("news_items", [])
        state["news_items"] = sorted(items, key=lambda item: item.get("score", 0), reverse=True)
        add_trace(state, "RerankAgent", {"items": len(items)}, "score_sort", f"重排候选新闻 {len(items)} 条")
        return state

    def _experiment_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        if state.get("intent") == "evaluation" and "evaluation_result" not in state:
            state["evaluation_result"] = self.container.experiment_service.evaluate_strategies()
        output = "运行策略评估" if state.get("intent") == "evaluation" else "当前任务无需运行实验"
        add_trace(state, "ExperimentAgent", {"intent": state.get("intent")}, "evaluate_strategies", output)
        return state

    def _answer_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        intent = state.get("intent")
        if intent == "document_qa":
            state["answer"] = state.get("rag_result", {}).get("answer", "")
        elif intent == "evaluation":
            state["answer"] = "已完成多策略推荐评估，可查看各策略在 HitRate、MRR、NDCG 上的表现。"
        elif intent == "daily_briefing":
            state["answer"] = state.get("answer", "")
        else:
            count = len(state.get("news_items", []))
            state["answer"] = f"已根据你的需求找到 {count} 篇相关新闻。"
            if state.get("rag_result", {}).get("citations"):
                state["answer"] += " 同时参考了你的本地资料库作为补充依据。"
        add_trace(state, "AnswerAgent", {"intent": intent}, "compose_answer", "生成最终回答")
        return state

    def _citation_verifier_agent(self, state: ResearchAgentState) -> ResearchAgentState:
        rag = state.get("rag_result") or {}
        verification = rag.get("verification") or {}
        if verification:
            output = verification.get("notes", "已检查引用")
        elif state.get("intent") == "document_qa":
            output = "没有可用引用，需谨慎展示。"
        else:
            output = "当前回答不依赖本地资料引用。"
        add_trace(state, "CitationVerifierAgent", {"citations": len(rag.get("citations", []))}, "verify_citations", output)
        return state


def add_trace(
    state: ResearchAgentState,
    agent: str,
    inputs: dict[str, Any],
    tool: str,
    output: str,
    details: Any | None = None,
) -> None:
    start = perf_counter()
    latency_ms = int((perf_counter() - start) * 1000)
    state.setdefault("workflow_trace", []).append(
        {
            "agent": agent,
            "input": inputs,
            "tool_calls": tool,
            "output": output,
            "latency_ms": latency_ms,
            "summary": output,
            "details": details,
        }
    )
