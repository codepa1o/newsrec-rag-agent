from __future__ import annotations

from typing import Any, TypedDict

from app.dependencies import ServiceContainer


class RecommendationState(TypedDict, total=False):
    user_id: str
    top_k: int
    profile: dict[str, Any]
    recommendations: list[dict[str, Any]]


class NewsRecommendationWorkflow:
    """LangGraph workflow with a deterministic fallback for local development."""

    def __init__(self, container: ServiceContainer) -> None:
        self.container = container
        self.graph = self._build_graph()

    def run(self, user_id: str, top_k: int = 10) -> RecommendationState:
        initial_state: RecommendationState = {"user_id": user_id, "top_k": top_k}
        if self.graph is None:
            state = self._load_user_profile(initial_state)
            state = self._retrieve_candidates(state)
            state = self._rerank_candidates(state)
            state = self._diversity_filter(state)
            state = self._generate_explanations(state)
            return state
        return self.graph.invoke(initial_state)

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:  # pragma: no cover - optional dependency
            return None

        graph = StateGraph(RecommendationState)
        graph.add_node("load_user_profile", self._load_user_profile)
        graph.add_node("retrieve_candidates", self._retrieve_candidates)
        graph.add_node("rerank_candidates", self._rerank_candidates)
        graph.add_node("diversity_filter", self._diversity_filter)
        graph.add_node("generate_explanations", self._generate_explanations)
        graph.set_entry_point("load_user_profile")
        graph.add_edge("load_user_profile", "retrieve_candidates")
        graph.add_edge("retrieve_candidates", "rerank_candidates")
        graph.add_edge("rerank_candidates", "diversity_filter")
        graph.add_edge("diversity_filter", "generate_explanations")
        graph.add_edge("generate_explanations", END)
        return graph.compile()

    def _load_user_profile(self, state: RecommendationState) -> RecommendationState:
        state["profile"] = self.container.recommender.get_profile(state["user_id"])
        return state

    def _retrieve_candidates(self, state: RecommendationState) -> RecommendationState:
        return state

    def _rerank_candidates(self, state: RecommendationState) -> RecommendationState:
        return state

    def _diversity_filter(self, state: RecommendationState) -> RecommendationState:
        return state

    def _generate_explanations(self, state: RecommendationState) -> RecommendationState:
        items = self.container.recommender.recommend(state["user_id"], top_k=state.get("top_k", 10))
        state["recommendations"] = [item.to_dict() for item in items]
        return state
