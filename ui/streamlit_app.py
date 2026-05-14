from __future__ import annotations

import base64
import html
import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
BACKGROUND_PATH = Path(__file__).parent / "assets" / "boki.png"
DEFAULT_USER = "U100"
DEFAULT_PASSWORD = "demo123456"


st.set_page_config(
    page_title="NewsRec-RAG Agent",
    page_icon="NR",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _background_data_uri() -> str:
    if not BACKGROUND_PATH.exists():
        return ""
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_styles() -> None:
    bg_uri = _background_data_uri()
    background_rule = (
        f"""
        background:
            linear-gradient(110deg, rgba(250, 247, 244, 0.92) 0%, rgba(244, 249, 250, 0.88) 50%, rgba(255, 246, 247, 0.90) 100%),
            url("{bg_uri}") center center / cover fixed;
        """
        if bg_uri
        else "background: linear-gradient(135deg, #faf7f4 0%, #eef7f8 52%, #fff1f2 100%);"
    )
    st.markdown(
        f"""
        <style>
        :root {{
            --bg: #faf7f4;
            --panel: rgba(255, 255, 255, 0.82);
            --panel-strong: rgba(255, 255, 255, 0.94);
            --line: rgba(42, 52, 57, 0.12);
            --text: #20272c;
            --muted: #687278;
            --soft: #f6f1ec;
            --accent: #9f3f5f;
            --accent-2: #18777f;
            --accent-3: #c58b32;
            --shadow: 0 18px 54px rgba(34, 42, 46, 0.13);
            --radius: 8px;
        }}

        .stApp {{
            {background_rule}
            color: var(--text);
        }}

        .block-container {{
            max-width: 1280px;
            padding: 1.25rem 1.6rem 3rem;
            animation: pageEnter 360ms ease-out both;
        }}

        @keyframes pageEnter {{
            from {{ opacity: 0; transform: translateY(12px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes softRise {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        [data-testid="stSidebar"] {{
            background: rgba(255, 255, 255, 0.90);
            border-right: 1px solid var(--line);
            backdrop-filter: blur(18px);
        }}

        [data-testid="stSidebar"] * {{
            letter-spacing: 0;
        }}

        h1, h2, h3, h4, p, label, span, div {{
            letter-spacing: 0;
        }}

        h1 {{
            font-size: 2rem;
            line-height: 1.18;
        }}

        h2 {{
            font-size: 1.45rem;
        }}

        h3 {{
            font-size: 1.12rem;
        }}

        .page-shell {{
            animation: softRise 300ms ease-out both;
        }}

        .hero {{
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: var(--panel);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
            padding: 1.05rem 1.1rem;
            margin-bottom: 1rem;
        }}

        .hero-kicker {{
            color: var(--accent-2);
            font-size: 0.82rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }}

        .hero-title {{
            margin: 0;
            font-size: clamp(1.55rem, 2.4vw, 2.25rem);
            line-height: 1.16;
            font-weight: 850;
            color: var(--text);
        }}

        .hero-subtitle {{
            max-width: 860px;
            margin: 0.45rem 0 0;
            color: var(--muted);
            line-height: 1.7;
            font-size: 0.98rem;
        }}

        .auth-wrap {{
            min-height: 78vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4vh 0;
        }}

        .auth-hero {{
            width: min(760px, 92vw);
            text-align: center;
            margin: 0 auto 1rem;
            animation: softRise 420ms ease-out both;
        }}

        .auth-badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.32rem 0.76rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid var(--line);
            color: var(--accent-2);
            font-size: 0.82rem;
            font-weight: 850;
        }}

        .auth-title {{
            margin: 0.8rem 0 0.45rem;
            font-size: clamp(2.15rem, 5vw, 4.35rem);
            line-height: 1.02;
            font-weight: 900;
            color: #1f2529;
            text-shadow: 0 12px 34px rgba(255, 255, 255, 0.65);
        }}

        .auth-copy {{
            max-width: 680px;
            margin: 0 auto;
            color: #4d575d;
            line-height: 1.75;
            font-size: 1.02rem;
        }}

        .metric-card {{
            min-height: 112px;
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: var(--panel-strong);
            box-shadow: 0 12px 32px rgba(34, 42, 46, 0.10);
            padding: 0.95rem;
        }}

        .metric-label {{
            color: var(--muted);
            font-size: 0.84rem;
            font-weight: 750;
        }}

        .metric-value {{
            margin-top: 0.24rem;
            font-size: 1.82rem;
            line-height: 1.1;
            font-weight: 900;
            color: var(--text);
        }}

        .metric-note {{
            margin-top: 0.28rem;
            color: var(--muted);
            font-size: 0.78rem;
        }}

        .article-card {{
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: var(--panel-strong);
            box-shadow: 0 12px 34px rgba(34, 42, 46, 0.09);
            padding: 0.95rem 1rem;
            margin: 0.75rem 0;
        }}

        .article-title {{
            margin: 0.35rem 0 0.4rem;
            font-size: 1.08rem;
            line-height: 1.4;
            font-weight: 850;
            color: var(--text);
        }}

        .article-abstract {{
            color: #4f5a60;
            line-height: 1.65;
            margin: 0.35rem 0 0.7rem;
        }}

        .reason-box {{
            border-left: 3px solid var(--accent-2);
            background: rgba(24, 119, 127, 0.08);
            border-radius: 0 var(--radius) var(--radius) 0;
            padding: 0.6rem 0.72rem;
            color: #32464a;
            line-height: 1.6;
        }}

        .pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            margin: 0 0.35rem 0.35rem 0;
            padding: 0.22rem 0.58rem;
            border-radius: 999px;
            border: 1px solid rgba(32, 39, 44, 0.10);
            background: rgba(246, 241, 236, 0.88);
            color: #435055;
            font-size: 0.78rem;
            font-weight: 760;
        }}

        .pill.accent {{
            background: rgba(159, 63, 95, 0.10);
            color: #82324f;
        }}

        .pill.teal {{
            background: rgba(24, 119, 127, 0.10);
            color: #17686f;
        }}

        .section-note {{
            color: var(--muted);
            line-height: 1.7;
            margin: -0.15rem 0 0.85rem;
        }}

        .trace-step {{
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: rgba(255, 255, 255, 0.78);
            padding: 0.65rem 0.75rem;
            margin: 0.5rem 0;
        }}

        .trace-agent {{
            font-weight: 850;
            color: var(--accent-2);
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: var(--radius);
            border-color: var(--line);
            background: var(--panel);
            box-shadow: 0 10px 34px rgba(34, 42, 46, 0.08);
            backdrop-filter: blur(16px);
        }}

        div.stButton > button,
        div.stDownloadButton > button,
        div.stLinkButton > a {{
            min-height: 2.5rem;
            border-radius: var(--radius);
            border: 1px solid rgba(32, 39, 44, 0.14);
            background: rgba(255, 255, 255, 0.86);
            color: var(--text);
            font-weight: 760;
            transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
        }}

        div.stButton > button:hover,
        div.stDownloadButton > button:hover,
        div.stLinkButton > a:hover {{
            transform: translateY(-1px);
            border-color: rgba(24, 119, 127, 0.34);
            background: #ffffff;
            box-shadow: 0 8px 22px rgba(34, 42, 46, 0.10);
            color: var(--accent-2);
        }}

        div.stButton > button[kind="primary"] {{
            border-color: transparent;
            background: linear-gradient(135deg, #1d777f, #9f3f5f);
            color: white;
        }}

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] div,
        [data-testid="stNumberInput"] input {{
            border-radius: var(--radius);
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.35rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: var(--radius);
            padding: 0.45rem 0.75rem;
            background: rgba(255, 255, 255, 0.62);
        }}

        @media (max-width: 760px) {{
            .block-container {{
                padding: 0.9rem 0.9rem 2rem;
            }}
            .auth-title {{
                font-size: 2.25rem;
            }}
            .metric-card {{
                min-height: 96px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()


SESSION_DEFAULTS = {
    "token": "",
    "user": None,
    "page": "系统仪表盘",
    "selected_news_id": "",
    "last_rag_result": None,
    "last_agent_result": None,
    "last_trace_result": None,
    "last_compare_result": None,
    "last_eval_result": None,
    "last_briefing": None,
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


def auth_headers() -> dict[str, str]:
    if not st.session_state.token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_get(path: str, auth: bool = False, timeout: int = 30) -> dict[str, Any]:
    response = httpx.get(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else None, timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any] | None = None, auth: bool = False, timeout: int = 60) -> dict[str, Any]:
    response = httpx.post(
        f"{API_BASE_URL}{path}",
        json=payload or {},
        headers=auth_headers() if auth else None,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def api_delete(path: str, auth: bool = False, timeout: int = 30) -> dict[str, Any]:
    response = httpx.delete(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else None, timeout=timeout)
    response.raise_for_status()
    return response.json()


def show_page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="page-shell">
          <section class="hero">
            <div class="hero-kicker">{_escape(kicker)}</div>
            <h1 class="hero-title">{_escape(title)}</h1>
            <p class="hero-subtitle">{_escape(subtitle)}</p>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: Any, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{_escape(label)}</div>
            <div class="metric-value">{_escape(value)}</div>
            <div class="metric-note">{_escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pills(items: list[Any], css_class: str = "") -> str:
    return "".join(f'<span class="pill {css_class}">{_escape(item)}</span>' for item in items if item)


def compact_number(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value or 0)
    if number >= 10000:
        return f"{number / 10000:.1f} 万"
    if number >= 1000:
        return f"{number / 1000:.1f}k"
    return str(number)


def extract_items(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    return payload.get("items", [])


def set_page(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def select_article(news_id: str) -> None:
    st.session_state.selected_news_id = news_id
    set_page("新闻详情")


def render_trace(trace: list[dict[str, Any]]) -> None:
    if not trace:
        st.info("暂无 Agent 运行轨迹。")
        return
    for index, step in enumerate(trace, start=1):
        agent = step.get("agent") or step.get("name") or f"Step {index}"
        output = step.get("output") or step.get("result") or step.get("summary") or ""
        action = step.get("action") or step.get("tool") or ""
        elapsed = step.get("elapsed_ms") or step.get("duration_ms") or ""
        st.markdown(
            f"""
            <div class="trace-step">
                <div class="trace-agent">{index}. {_escape(agent)}</div>
                <div>{_escape(action)}</div>
                <div>{_escape(output)}</div>
                <small>{_escape(str(elapsed) + " ms" if elapsed else "")}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_citations(citations: list[dict[str, Any]]) -> None:
    if not citations:
        st.info("暂无引用来源。")
        return
    for index, citation in enumerate(citations, start=1):
        filename = citation.get("filename") or citation.get("source") or "本地资料"
        location = citation.get("page") or citation.get("heading_path") or f"chunk {citation.get('chunk_index', '-')}"
        score = citation.get("score", "-")
        with st.expander(f"[{index}] {filename} · {location} · score={score}"):
            st.write(citation.get("snippet") or citation.get("text") or "")
            if citation.get("chunk_id"):
                st.caption(f"chunk_id: {citation['chunk_id']}")


def article_card(item: dict[str, Any], prefix: str, show_feedback: bool = True) -> None:
    news_id = item.get("news_id", "")
    title = item.get("title") or "未命名新闻"
    category = item.get("category") or "未知类别"
    score = item.get("score", "-")
    reason = item.get("reason", "")
    evidence = item.get("evidence") or []

    st.markdown('<div class="article-card">', unsafe_allow_html=True)
    st.markdown(
        pills([category], "teal")
        + pills([item.get("subcategory")], "")
        + pills([f"分数 {score}"], "accent")
        + pills([f"热度 {item.get('popularity')}"] if item.get("popularity") is not None else [], ""),
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="article-title">{_escape(title)}</div>', unsafe_allow_html=True)
    if item.get("abstract"):
        st.markdown(f'<p class="article-abstract">{_escape(item["abstract"])}</p>', unsafe_allow_html=True)
    if reason:
        st.markdown(f'<div class="reason-box">{_escape(reason)}</div>', unsafe_allow_html=True)
    if evidence:
        st.caption("证据：" + " | ".join(str(part) for part in evidence[:3]))

    button_cols = st.columns([1, 1, 1, 1])
    if button_cols[0].button("查看详情", key=f"{prefix}-detail-{news_id}", use_container_width=True):
        select_article(news_id)

    if show_feedback:
        if button_cols[1].button("喜欢", key=f"{prefix}-like-{news_id}", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "like"}, auth=True)
            st.toast("已记录喜欢反馈")
        if button_cols[2].button("不感兴趣", key=f"{prefix}-dislike-{news_id}", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "dislike"}, auth=True)
            st.toast("已记录不感兴趣反馈")
        if button_cols[3].button("屏蔽类别", key=f"{prefix}-block-{news_id}", use_container_width=True):
            api_post(
                "/me/feedback",
                {"news_id": news_id, "feedback_type": "block_category", "category": category},
                auth=True,
            )
            st.toast(f"已降低 {category} 类别推荐权重")
    else:
        button_cols[1].caption(f"新闻 ID：{news_id}")
    st.markdown("</div>", unsafe_allow_html=True)


def show_auth_page() -> None:
    st.markdown('<div class="auth-wrap"><div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="auth-hero">
          <span class="auth-badge">NewsRec-RAG Agent</span>
          <div class="auth-title">智能新闻推荐实验平台</div>
          <p class="auth-copy">
            面向新闻推荐系统研究：多策略推荐、离线评估、本地资料库 RAG、引用溯源和多 Agent 运行观测。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1.1, 1, 1.1])
    with center:
        with st.container(border=True):
            st.subheader("登录 / 注册")
            st.caption(f"演示账号：{DEFAULT_USER} / {DEFAULT_PASSWORD}")
            login_tab, register_tab = st.tabs(["登录", "注册"])

            with login_tab:
                username = st.text_input("用户名", value=DEFAULT_USER, key="login-username")
                password = st.text_input("密码", value=DEFAULT_PASSWORD, type="password", key="login-password")
                if st.button("进入系统", type="primary", use_container_width=True):
                    payload = api_post("/auth/login", {"username": username, "password": password})
                    st.session_state.token = payload["token"]
                    st.session_state.user = payload["user"]
                    st.session_state.page = "系统仪表盘"
                    st.rerun()

            with register_tab:
                new_username = st.text_input("用户名", key="register-username")
                display_name = st.text_input("昵称", key="register-display-name")
                new_password = st.text_input("密码", type="password", key="register-password")
                if st.button("创建账号", use_container_width=True):
                    api_post(
                        "/auth/register",
                        {"username": new_username, "password": new_password, "display_name": display_name or None},
                    )
                    st.success("注册成功，请切换到登录页进入系统。")
    st.markdown("</div></div>", unsafe_allow_html=True)


def sidebar() -> int:
    pages = [
        "系统仪表盘",
        "推荐",
        "新闻详情",
        "推荐策略对比",
        "实验评估",
        "兴趣漂移",
        "新闻事件聚类",
        "AI 新闻日报",
        "本地资料库",
        "资料库问答",
        "我的收藏",
        "浏览历史",
        "Agent 运行观测",
    ]
    user = st.session_state.user or {}
    with st.sidebar:
        st.markdown("### NewsRec-RAG")
        st.caption("Agentic RAG 新闻推荐平台")
        st.divider()
        st.markdown("**当前用户**")
        st.write(user.get("display_name") or user.get("username") or "未知用户")
        st.caption(f"用户 ID：{user.get('user_id', '-')}")
        top_k = st.slider("默认 TopK", min_value=5, max_value=50, value=20, step=5)
        st.divider()
        if st.session_state.page not in pages:
            st.session_state.page = "系统仪表盘"
        st.session_state.page = st.radio("导航", pages, index=pages.index(st.session_state.page), label_visibility="collapsed")
        st.divider()
        if st.button("退出登录", use_container_width=True):
            try:
                api_post("/auth/logout", {}, auth=True)
            finally:
                for key, default in SESSION_DEFAULTS.items():
                    st.session_state[key] = default
                st.rerun()
    return top_k


def show_dashboard() -> None:
    show_page_header("Overview", "系统仪表盘", "查看数据规模、用户行为、本地资料库和 RAG 查询等核心运行指标。")
    metrics = api_get("/metrics/overview")
    health = api_get("/health")

    cols = st.columns(4)
    with cols[0]:
        metric_card("新闻规模", compact_number(metrics.get("articles")), "MIND sample 新闻库")
    with cols[1]:
        metric_card("用户数", compact_number(metrics.get("users")), "注册和演示用户")
    with cols[2]:
        metric_card("本地资料", compact_number(metrics.get("documents")), f"{metrics.get('document_chunks', 0)} 个切片")
    with cols[3]:
        metric_card("RAG 查询", compact_number(metrics.get("rag_queries")), "带引用的资料库问答")

    cols = st.columns(4)
    with cols[0]:
        metric_card("浏览记录", compact_number(metrics.get("behaviors_tracked")), "进入详情页自动记录")
    with cols[1]:
        metric_card("反馈事件", compact_number(metrics.get("feedback_events")), "喜欢 / 不感兴趣 / 屏蔽")
    with cols[2]:
        metric_card("收藏数", compact_number(metrics.get("favorites")), "用户收藏关系")
    with cols[3]:
        metric_card("AI 模式", "DashScope" if health.get("use_dashscope") else "Fallback", "无 Key 也可演示")

    left, right = st.columns([1.1, 1])
    with left:
        with st.container(border=True):
            st.subheader("新闻类别分布")
            top_categories = metrics.get("top_categories", [])
            if not top_categories:
                st.info("暂无类别统计。")
            else:
                max_count = max(count for _, count in top_categories) or 1
                for category, count in top_categories:
                    st.caption(f"{category} · {count}")
                    st.progress(min(count / max_count, 1.0))

    with right:
        with st.container(border=True):
            st.subheader("系统能力总览")
            capabilities = [
                "多策略新闻推荐与 TopK 对比",
                "HitRate / MRR / NDCG 离线评估",
                "Markdown / TXT / PDF 本地资料库 RAG",
                "引用来源、可信度与幻觉控制",
                "Planner / Router / Retriever / Verifier 多 Agent Trace",
            ]
            for item in capabilities:
                st.markdown(f"- {item}")
            st.caption(f"生成时间：{metrics.get('generated_at', '-')}")


def show_recommendations(top_k: int) -> None:
    show_page_header("Recommendation", "个性化推荐", "结合点击历史、收藏、反馈、本地资料主题和多样性过滤生成新闻推荐。")
    profile = api_get("/me/profile", auth=True)
    recommendations = api_get(f"/me/recommend?top_k={top_k}", auth=True)["items"]

    profile_col, action_col = st.columns([1.35, 1])
    with profile_col:
        with st.container(border=True):
            st.subheader("用户兴趣画像")
            st.markdown(pills(profile.get("preferred_categories", []), "teal"), unsafe_allow_html=True)
            st.markdown(pills(profile.get("keywords", []), "accent"), unsafe_allow_html=True)
            blocked = profile.get("blocked_categories", [])
            if blocked:
                st.warning("已屏蔽类别：" + "、".join(blocked))

    with action_col:
        with st.container(border=True):
            st.subheader("AI 画像总结")
            if st.button("生成中文画像总结", type="primary", use_container_width=True):
                summary = api_get("/me/profile/summary", auth=True, timeout=60)
                st.write(summary.get("summary", "暂无总结"))
            else:
                st.caption("点击后将基于近期点击、收藏和反馈生成自然语言画像。")

    st.subheader("推荐新闻流")
    for item in recommendations:
        article_card(item, "rec")


def show_article_detail() -> None:
    show_page_header("Article", "新闻详情", "查看站内详情、推荐理由、AI 摘要、问答、本地资料解读和同事件相关新闻。")
    news_id = st.session_state.selected_news_id
    if not news_id:
        st.info("请先在推荐页、收藏页、历史页或事件聚类页点击一篇新闻。")
        return

    api_post(f"/me/articles/{news_id}/view", {}, auth=True)
    detail = api_get(f"/me/articles/{news_id}", auth=True)
    article = detail.get("article", {})

    with st.container(border=True):
        st.markdown(
            pills([article.get("category"), article.get("subcategory")], "teal") + pills([article.get("news_id")], "accent"),
            unsafe_allow_html=True,
        )
        st.subheader(article.get("title", "未命名新闻"))
        st.write(article.get("abstract") or "暂无摘要。")
        st.markdown(f'<div class="reason-box">{_escape(detail.get("reason", "暂无推荐理由"))}</div>', unsafe_allow_html=True)

        cols = st.columns(6)
        favorite_label = "取消收藏" if detail.get("favorite") else "收藏新闻"
        if cols[0].button(favorite_label, use_container_width=True):
            api_post(f"/me/articles/{news_id}/favorite", {"favorite": not detail.get("favorite")}, auth=True)
            st.rerun()
        if cols[1].button("喜欢", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "like"}, auth=True)
            st.toast("已记录喜欢反馈")
        if cols[2].button("不感兴趣", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "dislike"}, auth=True)
            st.toast("已记录不感兴趣反馈")
        if cols[3].button("同事件", use_container_width=True):
            set_page("新闻事件聚类")
        if cols[4].button("资料解读", use_container_width=True):
            st.session_state.last_rag_result = api_post(f"/me/articles/{news_id}/grounded-analysis", {}, auth=True, timeout=90)
        if article.get("url"):
            cols[5].link_button("查看原文", article["url"], use_container_width=True)
        else:
            cols[5].caption("暂无原文")

    if st.session_state.last_rag_result:
        result = st.session_state.last_rag_result
        with st.container(border=True):
            st.subheader("本地资料解读")
            st.write(result.get("answer", ""))
            st.caption(f"可信度：{result.get('confidence', '-')} | 证据不足：{result.get('missing_evidence', '-')}")
            render_citations(result.get("citations", []))
            with st.expander("Agent 工作流"):
                render_trace(result.get("workflow_trace", []))

    summary_col, ask_col = st.columns(2)
    with summary_col:
        with st.container(border=True):
            st.subheader("AI 新闻摘要")
            if st.button("生成摘要", type="primary", use_container_width=True):
                summary = api_post(f"/me/articles/{news_id}/summary", {}, auth=True)
                st.write(summary.get("one_sentence", "暂无摘要"))
                for point in summary.get("key_points", []):
                    st.markdown(f"- {point}")
                if summary.get("audience"):
                    st.caption("适合人群：" + summary["audience"])

    with ask_col:
        with st.container(border=True):
            st.subheader("围绕新闻提问")
            question = st.text_area("问题", placeholder="例如：这篇新闻为什么值得推荐给我？")
            if st.button("提交问题", use_container_width=True):
                if not question.strip():
                    st.warning("请输入问题。")
                else:
                    answer = api_post(f"/me/articles/{news_id}/ask", {"question": question}, auth=True, timeout=60)
                    st.write(answer.get("answer", "暂无回答"))

    related = detail.get("related", [])
    if related:
        st.subheader("相关新闻")
        for item in related:
            article_card(item, "related")


def show_strategy_compare(top_k: int) -> None:
    show_page_header("Experiment", "推荐策略对比", "同一用户下横向比较热门、类别偏好、向量语义、反馈增强和 Agentic RAG 推荐。")
    user = st.session_state.user or {}
    with st.container(border=True):
        query = st.text_input("可选检索意图", placeholder="例如：AI regulation, sports, finance")
        run = st.button("运行策略对比", type="primary", use_container_width=True)
    if run or not st.session_state.last_compare_result:
        st.session_state.last_compare_result = api_post(
            "/recommend/compare",
            {"user_id": user.get("user_id", DEFAULT_USER), "top_k": top_k, "query": query or None},
            timeout=90,
        )

    result = st.session_state.last_compare_result
    for strategy in result.get("strategies", []):
        with st.expander(strategy.get("label", strategy.get("name", "策略")), expanded=strategy.get("name") == "agentic_rag"):
            st.caption("类别分布：" + str(result.get("category_distribution", {}).get(strategy.get("name"), {})))
            for item in strategy.get("items", [])[:top_k]:
                article_card(item, f"compare-{strategy.get('name')}", show_feedback=False)


def show_strategy_evaluation() -> None:
    show_page_header("Evaluation", "实验评估", "运行 HitRate@K、MRR@K、NDCG@K，对推荐策略做可解释的离线对比。")
    with st.container(border=True):
        options = st.multiselect("K 值", options=[3, 5, 10, 20, 50], default=[5, 10, 20])
        if st.button("运行多策略评估", type="primary", use_container_width=True):
            st.session_state.last_eval_result = api_post("/evaluate/strategies", {"k_values": options or [5, 10, 20]}, timeout=120)

    result = st.session_state.last_eval_result
    if not result:
        st.info("点击按钮后开始评估。")
        return

    best_cols = st.columns(len(result.get("best_by_k", {})) or 1)
    for col, (k, row) in zip(best_cols, result.get("best_by_k", {}).items()):
        with col:
            metric_card(f"K={k} 最优策略", row.get("label", "-"), f"NDCG {row.get('ndcg', '-')}")

    for strategy, rows in result.get("results", {}).items():
        with st.expander(rows[0].get("label", strategy) if rows else strategy, expanded=strategy == "agentic_rag"):
            st.table(rows)


def show_interest_drift() -> None:
    show_page_header("User Modeling", "兴趣漂移", "展示长期兴趣与近期兴趣的差异，帮助解释推荐系统如何动态调整用户画像。")
    drift = api_get("/me/interest-drift", auth=True)
    st.info(drift.get("summary", "暂无总结"))
    cols = st.columns(3)
    with cols[0]:
        with st.container(border=True):
            st.subheader("长期关键词")
            st.markdown(pills(drift.get("long_term_keywords", []), "teal"), unsafe_allow_html=True)
    with cols[1]:
        with st.container(border=True):
            st.subheader("近期关键词")
            st.markdown(pills(drift.get("recent_keywords", []), "accent"), unsafe_allow_html=True)
    with cols[2]:
        with st.container(border=True):
            st.subheader("新兴 / 衰减")
            st.caption("新兴主题")
            st.markdown(pills(drift.get("emerging_keywords", []), "teal"), unsafe_allow_html=True)
            st.caption("可能衰减")
            st.markdown(pills(drift.get("fading_keywords", []), ""), unsafe_allow_html=True)


def show_event_cluster() -> None:
    show_page_header("News Intelligence", "新闻事件聚类", "围绕当前新闻查找同事件相关新闻，并生成不同报道角度的简要对比。")
    news_id = st.session_state.selected_news_id
    with st.container(border=True):
        news_id = st.text_input("新闻 ID", value=news_id, placeholder="例如：N12345")
        top_k = st.slider("同事件数量", min_value=3, max_value=15, value=8)
        run = st.button("分析事件聚类", type="primary", use_container_width=True)
    if not news_id:
        st.info("可以先从推荐流点击一篇新闻，或手动输入新闻 ID。")
        return
    if run:
        st.session_state.selected_news_id = news_id
    cluster = api_get(f"/articles/{news_id}/event-cluster?top_k={top_k}")
    viewpoints = api_get(f"/articles/{news_id}/viewpoints?top_k={min(top_k, 8)}")
    st.info(cluster.get("summary", ""))
    st.markdown(pills(cluster.get("event_keywords", []), "teal"), unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("观点角度")
        st.write(viewpoints.get("summary", ""))
        st.table(viewpoints.get("viewpoints", []))
    for item in cluster.get("items", []):
        article_card(item, "cluster", show_feedback=False)


def show_daily_briefing() -> None:
    show_page_header("AI Briefing", "AI 新闻日报", "根据你的画像生成个性化中文简报，包含推荐新闻、阅读顺序和推荐理由。")
    with st.container(border=True):
        top_k = st.slider("日报新闻数量", min_value=3, max_value=20, value=8)
        if st.button("生成今日简报", type="primary", use_container_width=True):
            st.session_state.last_briefing = api_post("/me/daily-briefing", {"top_k": top_k}, auth=True, timeout=90)
    briefing = st.session_state.last_briefing
    if not briefing:
        st.info("点击按钮后生成个性化新闻日报。")
        return
    with st.container(border=True):
        st.subheader(briefing.get("title", "今日个性化新闻简报"))
        st.write(briefing.get("briefing", "暂无简报"))
        st.markdown(pills(briefing.get("profile_keywords", []), "accent"), unsafe_allow_html=True)
    for item in briefing.get("items", []):
        article_card(item, "briefing")


def show_documents() -> None:
    show_page_header("Local RAG", "本地资料库", "上传 Markdown、TXT、PDF，系统自动解析、切分、索引，并在问答与新闻解读中引用来源。")
    with st.container(border=True):
        uploaded = st.file_uploader("上传资料", type=["md", "markdown", "txt", "pdf"])
        if uploaded and st.button("写入资料库", type="primary", use_container_width=True):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
            response = httpx.post(
                f"{API_BASE_URL}/me/documents/upload",
                files=files,
                headers=auth_headers(),
                timeout=180,
            )
            response.raise_for_status()
            st.success(response.json().get("message", "上传成功"))
            st.rerun()

    documents = api_get("/me/documents", auth=True)["items"]
    if not documents:
        st.info("还没有上传资料。")
        return
    for document in documents:
        with st.container(border=True):
            st.subheader(document.get("filename", "未命名文档"))
            st.write(
                f"状态：{document.get('status', '-')} | 切片数：{document.get('chunk_count', 0)} | "
                f"更新时间：{document.get('updated_at', '-')}"
            )
            if document.get("error_message"):
                st.warning(document["error_message"])
            cols = st.columns(3)
            doc_id = document.get("document_id")
            if cols[0].button("查看切片", key=f"doc-view-{doc_id}", use_container_width=True):
                detail = api_get(f"/me/documents/{doc_id}", auth=True)
                st.json(detail.get("chunks", []))
            if cols[1].button("重新索引", key=f"doc-reindex-{doc_id}", use_container_width=True):
                st.write(api_post(f"/me/documents/{doc_id}/reindex", {}, auth=True, timeout=120))
                st.rerun()
            if cols[2].button("删除", key=f"doc-delete-{doc_id}", use_container_width=True):
                api_delete(f"/me/documents/{doc_id}", auth=True)
                st.rerun()


def show_rag_query() -> None:
    show_page_header("Grounded QA", "资料库问答", "支持向量检索 + 关键词检索的混合 RAG，回答时展示引用来源、可信度和答案评估。")
    documents = api_get("/me/documents", auth=True)["items"]
    doc_options = {"全部资料": None}
    doc_options.update({item.get("filename", item["document_id"]): item["document_id"] for item in documents})

    with st.container(border=True):
        question = st.text_area("问题", placeholder="例如：资料中如何讨论 AI 监管和推荐系统合规？")
        selected_doc = st.selectbox("检索范围", list(doc_options.keys()))
        top_k = st.slider("引用片段数量", min_value=1, max_value=12, value=5)
        mode = st.radio("检索模式", ["混合检索", "向量检索"], horizontal=True)
        if st.button("开始问答", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("请输入问题。")
            else:
                endpoint = "/me/rag/hybrid-query" if mode == "混合检索" else "/me/rag/query"
                st.session_state.last_rag_result = api_post(
                    endpoint,
                    {"question": question, "top_k": top_k, "document_id": doc_options[selected_doc]},
                    auth=True,
                    timeout=120,
                )

    result = st.session_state.last_rag_result
    if result:
        with st.container(border=True):
            st.subheader("回答")
            st.write(result.get("answer", ""))
            st.caption(
                f"可信度：{result.get('confidence', '-')} | "
                f"证据不足：{result.get('missing_evidence', '-')} | "
                f"检索模式：{result.get('retrieval_mode', '-')}"
            )
            st.subheader("引用来源")
            render_citations(result.get("citations", []))
            st.subheader("答案评估")
            st.json(result.get("evaluation", {}))
            with st.expander("多 Agent 运行轨迹"):
                render_trace(result.get("workflow_trace", []))


def show_collection(path: str, title: str, subtitle: str, empty_message: str) -> None:
    show_page_header("User Library", title, subtitle)
    items = extract_items(api_get(path, auth=True))
    if not items:
        st.info(empty_message)
        return
    for item in items:
        article_card(item, path.replace("/", "-"))


def show_agent_observability(top_k_default: int) -> None:
    show_page_header("Multi-Agent", "Agent 运行观测", "查看 Planner、Router、Retriever、Reranker、Answer、Verifier 等 Agent 的输入输出链路。")
    with st.container(border=True):
        query = st.text_area(
            "输入任务",
            placeholder="例如：结合我上传的资料，推荐几篇 AI 监管相关的新闻，并说明推荐依据。",
        )
        top_k = st.slider("返回数量", min_value=1, max_value=20, value=min(top_k_default, 8))
        if st.button("运行并展示 Trace", type="primary", use_container_width=True):
            if not query.strip():
                st.warning("请输入任务。")
            else:
                st.session_state.last_trace_result = api_post(
                    "/me/agent/trace",
                    {"query": query, "top_k": top_k},
                    auth=True,
                    timeout=120,
                )

    result = st.session_state.last_trace_result
    if not result:
        st.info("运行后这里会展示完整 Agent trace。")
        return
    with st.container(border=True):
        st.subheader("最终回答")
        st.write(result.get("answer", ""))
        st.caption(f"识别意图：{result.get('intent', '-')}")
        if result.get("evaluation"):
            st.json(result["evaluation"])
    with st.container(border=True):
        st.subheader("运行轨迹")
        render_trace(result.get("workflow_trace", []))
    if result.get("rag", {}).get("citations"):
        with st.container(border=True):
            st.subheader("资料引用")
            render_citations(result["rag"]["citations"])
    if result.get("items"):
        st.subheader("相关新闻")
        for item in result["items"]:
            article_card(item, "agent-trace")


def show_app() -> None:
    top_k = sidebar()
    page = st.session_state.page
    if page == "系统仪表盘":
        show_dashboard()
    elif page == "推荐":
        show_recommendations(top_k)
    elif page == "新闻详情":
        show_article_detail()
    elif page == "推荐策略对比":
        show_strategy_compare(top_k)
    elif page == "实验评估":
        show_strategy_evaluation()
    elif page == "兴趣漂移":
        show_interest_drift()
    elif page == "新闻事件聚类":
        show_event_cluster()
    elif page == "AI 新闻日报":
        show_daily_briefing()
    elif page == "本地资料库":
        show_documents()
    elif page == "资料库问答":
        show_rag_query()
    elif page == "我的收藏":
        show_collection("/me/favorites", "我的收藏", "管理你标记的重要新闻，收藏会进入兴趣画像。", "还没有收藏新闻。")
    elif page == "浏览历史":
        show_collection("/me/history", "浏览历史", "系统会用近期浏览行为分析兴趣漂移。", "还没有浏览历史。")
    elif page == "Agent 运行观测":
        show_agent_observability(top_k)


try:
    if st.session_state.token:
        show_app()
    else:
        show_auth_page()
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        st.session_state.token = ""
        st.session_state.user = None
        st.error("登录状态已失效，请重新登录。")
        st.rerun()
    try:
        detail = exc.response.json().get("detail", "请求失败")
    except ValueError:
        detail = exc.response.text or "请求失败"
    st.error(detail)
except httpx.HTTPError as exc:
    st.error(f"后端服务不可用：{exc}")
    st.code(".\\run_dev.ps1")
