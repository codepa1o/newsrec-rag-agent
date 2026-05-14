from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.models import Article, UserProfile
from app.services.database import Database


def stable_key(*parts: str) -> str:
    content = "\n".join(parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class LLMService:
    settings: Settings
    database: Database

    def summarize_article(self, article: Article) -> dict[str, Any]:
        cache_key = stable_key(article.news_id, article.title, article.abstract)
        cached = self._get_cached_json("article_summary", cache_key)
        if cached:
            return cached

        prompt = (
            "请用中文为下面这篇新闻生成结构化摘要，返回 JSON，字段为 "
            "one_sentence、key_points、audience。"
            f"\n标题：{article.title}\n摘要：{article.abstract}\n类别：{article.category}/{article.subcategory}"
        )
        content = self._chat(prompt)
        result = self._parse_summary_json(content, self._fallback_summary(article))
        self._set_cached_json("article_summary", cache_key, result)
        return result

    def answer_article_question(self, article: Article, question: str) -> dict[str, str]:
        cache_key = stable_key(article.news_id, question, article.title, article.abstract)
        cached = self._get_cached_json("article_qa", cache_key)
        if cached:
            return cached

        prompt = (
            "你是新闻推荐系统中的阅读助手。请只基于给定新闻内容回答用户问题。"
            "如果新闻内容不足以回答，请明确说明信息不足。"
            f"\n标题：{article.title}\n摘要：{article.abstract}\n类别：{article.category}/{article.subcategory}"
            f"\n用户问题：{question}"
        )
        answer = self._chat(prompt)
        result = {"answer": answer or self._fallback_answer(article, question)}
        self._set_cached_json("article_qa", cache_key, result)
        return result

    def explain_recommendation(self, article: Article, profile: UserProfile, rule_reason: str) -> dict[str, str]:
        profile_text = (
            f"偏好类别：{', '.join(profile.preferred_categories) or '暂无'}；"
            f"关键词：{', '.join(profile.keywords[:8]) or '暂无'}；"
            f"近期点击：{', '.join(profile.recent_clicked_news[:8]) or '暂无'}"
        )
        cache_key = stable_key(article.news_id, profile.user_id, profile_text, rule_reason)
        cached = self._get_cached_json("recommendation_explanation", cache_key)
        if cached:
            return cached

        prompt = (
            "请用自然、可信的中文解释为什么新闻推荐系统会把这篇新闻推荐给用户。"
            "不要夸张，不要编造新闻正文之外的信息，控制在 80 字以内。"
            f"\n用户画像：{profile_text}\n规则理由：{rule_reason}"
            f"\n新闻标题：{article.title}\n新闻摘要：{article.abstract}"
        )
        explanation = self._chat(prompt)
        result = {"explanation": explanation or rule_reason}
        self._set_cached_json("recommendation_explanation", cache_key, result)
        return result

    def summarize_profile(self, profile: UserProfile) -> dict[str, str]:
        profile_text = json.dumps(profile.to_dict(), ensure_ascii=False, sort_keys=True)
        cache_key = stable_key(profile.user_id, profile_text)
        cached = self._get_cached_json("profile_summary", cache_key)
        if cached:
            return cached

        prompt = (
            "请根据用户新闻兴趣画像，生成一段中文画像总结，并给出 2 条推荐策略建议。"
            f"\n用户画像 JSON：{profile_text}"
        )
        summary = self._chat(prompt)
        result = {"summary": summary or self._fallback_profile_summary(profile)}
        self._set_cached_json("profile_summary", cache_key, result)
        return result

    def grounded_answer(self, question: str, contexts: list[dict[str, Any]]) -> str:
        if not contexts:
            return ""
        context_text = "\n\n".join(
            f"[{index}] 来源：{item['filename']}；页码/标题：{item.get('page') or item.get('heading_path') or '无'}；"
            f"片段：{item['text'][:1000]}"
            for index, item in enumerate(contexts, start=1)
        )
        cache_key = stable_key("grounded_answer", question, context_text)
        cached = self._get_cached_json("grounded_answer", cache_key)
        if cached and cached.get("answer"):
            return str(cached["answer"])

        prompt = (
            "你是严谨的本地资料库 RAG 助手。请只根据给定资料片段回答问题。"
            "回答必须包含引用编号，例如 [1]、[2]。如果资料不足，请直接说明本地资料中没有找到足够依据。"
            f"\n用户问题：{question}\n\n资料片段：\n{context_text}"
        )
        answer = self._chat(prompt)
        if answer:
            self._set_cached_json("grounded_answer", cache_key, {"answer": answer})
        return answer

    def _chat(self, prompt: str) -> str:
        if not self.settings.use_dashscope or not self.settings.dashscope_api_key:
            return ""

        base_url = self.settings.dashscope_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "你是一个严谨的中文新闻推荐与资料库问答助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=self.settings.ai_timeout_seconds)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def _get_cached_json(self, task: str, cache_key: str) -> dict[str, Any] | None:
        if not self.settings.ai_cache_enabled:
            return None
        cached = self.database.get_cached_ai(task, cache_key)
        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    def _set_cached_json(self, task: str, cache_key: str, value: dict[str, Any]) -> None:
        if self.settings.ai_cache_enabled:
            self.database.set_cached_ai(task, cache_key, json.dumps(value, ensure_ascii=False))

    def _parse_summary_json(self, content: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not content:
            return fallback
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return {
                    "one_sentence": str(parsed.get("one_sentence") or fallback["one_sentence"]),
                    "key_points": list(parsed.get("key_points") or fallback["key_points"])[:5],
                    "audience": str(parsed.get("audience") or fallback["audience"]),
                }
        except json.JSONDecodeError:
            pass
        return {**fallback, "one_sentence": content[:180]}

    def _fallback_summary(self, article: Article) -> dict[str, Any]:
        return {
            "one_sentence": article.abstract or article.title,
            "key_points": [
                f"这是一篇{article.category}类新闻。",
                "系统基于标题、摘要和用户兴趣进行语义匹配。",
                "配置 DashScope API Key 后可生成更完整的 AI 摘要。",
            ],
            "audience": f"适合关注{article.category}、{article.subcategory}相关内容的用户阅读。",
        }

    def _fallback_answer(self, article: Article, question: str) -> str:
        return (
            "当前未启用 DashScope API，因此使用本地 fallback 回答。"
            f"这篇新闻的标题是《{article.title}》，摘要为：{article.abstract or '暂无摘要'}。"
            "你可以配置 DASHSCOPE_API_KEY 获取更完整的新闻问答能力。"
        )

    def _fallback_profile_summary(self, profile: UserProfile) -> str:
        categories = "、".join(profile.preferred_categories) or "暂无明显类别偏好"
        keywords = "、".join(profile.keywords[:6]) or "暂无明显关键词"
        return f"用户近期偏好类别为：{categories}；关注关键词包括：{keywords}。建议继续混合推荐兴趣相关内容和少量探索内容。"
