from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
BACKGROUND_PATH = Path(__file__).parent / "assets" / "boki.png"


st.set_page_config(page_title="智能新闻推荐系统", layout="wide")


def background_data_uri() -> str:
    if not BACKGROUND_PATH.exists():
        return ""
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_styles() -> None:
    bg_uri = background_data_uri()
    background_rule = (
        f"""
        background:
            linear-gradient(90deg, rgba(255,255,255,0.78), rgba(255,246,250,0.74)),
            url("{bg_uri}") center center / cover fixed;
        """
        if bg_uri
        else "background: linear-gradient(135deg, #fff7fb 0%, #f4f8ff 100%);"
    )
    st.markdown(
        f"""
        <style>
        :root {{
            --panel: rgba(255, 255, 255, 0.84);
            --border: rgba(145, 92, 124, 0.18);
            --text: #2b2430;
            --muted: #6f6473;
            --accent: #b44f7a;
            --accent-dark: #8e3d62;
            --soft: rgba(180, 79, 122, 0.10);
        }}
        .stApp {{
            {background_rule}
            color: var(--text);
        }}
        .block-container {{
            max-width: 1200px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }}
        [data-testid="stSidebar"] {{
            background: rgba(255, 255, 255, 0.86);
            border-right: 1px solid var(--border);
            backdrop-filter: blur(18px);
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 18px 48px rgba(74, 45, 68, 0.13);
            backdrop-filter: blur(16px);
        }}
        .auth-hero {{
            width: min(720px, 92vw);
            margin: 7vh auto 1.4rem auto;
            text-align: center;
            padding: 1.3rem 1.1rem 0.2rem 1.1rem;
        }}
        .auth-kicker {{
            display: inline-block;
            padding: 0.25rem 0.7rem;
            border: 1px solid var(--border);
            border-radius: 999px;
            background: rgba(255,255,255,0.68);
            color: var(--accent-dark);
            font-size: 0.82rem;
            font-weight: 700;
        }}
        .auth-title {{
            margin: 0.8rem 0 0.35rem 0;
            font-size: clamp(2.2rem, 5vw, 4rem);
            line-height: 1.05;
            font-weight: 850;
            letter-spacing: 0;
            color: #2e2130;
            text-shadow: 0 8px 24px rgba(255,255,255,0.55);
        }}
        .auth-subtitle {{
            margin: 0 auto;
            max-width: 640px;
            color: #5c4f5e;
            font-size: 1.02rem;
            line-height: 1.7;
        }}
        .card-title {{
            font-size: 1.28rem;
            font-weight: 800;
            color: var(--text);
            margin-bottom: 0.2rem;
        }}
        .card-muted {{
            color: var(--muted);
            font-size: 0.92rem;
            margin-bottom: 0.9rem;
        }}
        .app-hero {{
            padding: 1.05rem 1.15rem;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--panel);
            box-shadow: 0 18px 44px rgba(74, 45, 68, 0.11);
            backdrop-filter: blur(16px);
            margin-bottom: 1rem;
        }}
        .app-hero h1 {{
            margin: 0 0 0.25rem 0;
            font-size: 1.9rem;
            line-height: 1.2;
            letter-spacing: 0;
            color: var(--text);
        }}
        .app-hero p {{
            margin: 0;
            color: var(--muted);
        }}
        .meta-pill {{
            display: inline-flex;
            align-items: center;
            margin: 0 0.35rem 0.45rem 0;
            padding: 0.22rem 0.62rem;
            border-radius: 999px;
            background: var(--soft);
            color: var(--accent-dark);
            font-size: 0.82rem;
            font-weight: 700;
        }}
        div.stButton > button,
        div.stLinkButton > a {{
            border-radius: 8px;
            border: 1px solid rgba(180, 79, 122, 0.24);
            background: rgba(255, 255, 255, 0.78);
            color: var(--text);
            min-height: 2.45rem;
            font-weight: 700;
        }}
        div.stButton > button:hover,
        div.stLinkButton > a:hover {{
            border-color: rgba(180, 79, 122, 0.48);
            background: rgba(255, 246, 250, 0.94);
            color: var(--accent-dark);
        }}
        div.stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, #b44f7a, #d46f91);
            color: white;
            border-color: transparent;
        }}
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {{
            border-radius: 8px;
            border-color: rgba(145, 92, 124, 0.22);
            background: rgba(255, 255, 255, 0.88);
        }}
        h1, h2, h3 {{
            letter-spacing: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()

for key, default in {
    "token": "",
    "user": None,
    "page": "推荐",
    "selected_news_id": "",
    "last_rag_result": None,
    "last_agent_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def auth_headers() -> dict[str, str]:
    if not st.session_state.token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_get(path: str, auth: bool = False) -> dict:
    response = httpx.get(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else None, timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None, auth: bool = False) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}{path}",
        json=payload or {},
        headers=auth_headers() if auth else None,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def api_delete(path: str, auth: bool = False) -> dict:
    response = httpx.delete(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else None, timeout=30)
    response.raise_for_status()
    return response.json()


def render_app_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_citations(citations: list[dict]) -> None:
    if not citations:
        st.info("暂无可引用来源。")
        return
    for index, citation in enumerate(citations, start=1):
        location = citation.get("page") or citation.get("heading_path") or f"chunk {citation.get('chunk_index')}"
        with st.expander(f"[{index}] {citation.get('filename')} · {location} · score={citation.get('score')}"):
            st.write(citation.get("snippet", ""))
            st.caption(f"chunk_id: {citation.get('chunk_id')}")


def render_trace(trace: list[dict]) -> None:
    if not trace:
        return
    with st.expander("多 Agent 运行轨迹", expanded=True):
        for step in trace:
            st.markdown(f"**{step.get('agent')}**：{step.get('output')}")


def select_article(news_id: str) -> None:
    st.session_state.selected_news_id = news_id
    st.session_state.page = "新闻详情"
    st.rerun()


def show_auth_page() -> None:
    st.markdown(
        """
        <div class="auth-hero">
            <div class="auth-kicker">NewsRec-RAG Agent V3</div>
            <div class="auth-title">智能新闻推荐系统</div>
            <p class="auth-subtitle">
                登录后查看个性化新闻、AI 摘要、本地资料库 RAG、引用溯源和多 Agent 推荐助手。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.08, 1])
    with center:
        with st.container(border=True):
            st.markdown('<div class="card-title">欢迎回来</div>', unsafe_allow_html=True)
            st.markdown('<div class="card-muted">演示账号：U100 / demo123456</div>', unsafe_allow_html=True)
            login_tab, register_tab = st.tabs(["登录", "注册"])

            with login_tab:
                username = st.text_input("用户名", value="U100", key="login-username")
                password = st.text_input("密码", value="demo123456", type="password", key="login-password")
                if st.button("登录", type="primary", use_container_width=True):
                    try:
                        payload = api_post("/auth/login", {"username": username, "password": password})
                        st.session_state.token = payload["token"]
                        st.session_state.user = payload["user"]
                        st.session_state.page = "推荐"
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "登录失败"))
                    except httpx.HTTPError as exc:
                        st.error(f"无法连接后端服务：{exc}")

            with register_tab:
                new_username = st.text_input("用户名", key="register-username")
                display_name = st.text_input("昵称", key="register-display-name")
                new_password = st.text_input("密码", type="password", key="register-password")
                if st.button("注册", use_container_width=True):
                    try:
                        api_post(
                            "/auth/register",
                            {"username": new_username, "password": new_password, "display_name": display_name or None},
                        )
                        st.success("注册成功，请回到登录页登录。")
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "注册失败"))
                    except httpx.HTTPError as exc:
                        st.error(f"无法连接后端服务：{exc}")


def sidebar() -> int:
    user = st.session_state.user or {}
    with st.sidebar:
        st.header("当前用户")
        st.write(user.get("display_name", user.get("username", "未知用户")))
        st.caption(f"用户 ID：{user.get('user_id', '-')}")
        top_k = st.slider("推荐数量", min_value=5, max_value=50, value=20)
        pages = ["推荐", "新闻详情", "本地资料库", "资料库问答", "我的收藏", "浏览历史", "多 Agent 助手", "评估看板"]
        if st.session_state.page not in pages:
            st.session_state.page = "推荐"
        st.session_state.page = st.radio("导航", pages, index=pages.index(st.session_state.page))
        if st.button("退出登录", use_container_width=True):
            try:
                api_post("/auth/logout", {}, auth=True)
            finally:
                st.session_state.token = ""
                st.session_state.user = None
                st.session_state.selected_news_id = ""
                st.rerun()
    return top_k


def article_card(item: dict, prefix: str) -> None:
    with st.container(border=True):
        st.markdown(
            f"""
            <span class="meta-pill">{item.get('category', '未知类别')}</span>
            <span class="meta-pill">推荐分 {item.get('score', '-')}</span>
            """,
            unsafe_allow_html=True,
        )
        if st.button(item["title"], key=f"{prefix}-title-{item['news_id']}", use_container_width=True):
            select_article(item["news_id"])
        if item.get("abstract"):
            st.write(item["abstract"])
        if item.get("reason"):
            st.info(item["reason"])
        feedback_cols = st.columns(3)
        if feedback_cols[0].button("喜欢", key=f"{prefix}-like-{item['news_id']}", use_container_width=True):
            api_post("/me/feedback", {"news_id": item["news_id"], "feedback_type": "like"}, auth=True)
            st.rerun()
        if feedback_cols[1].button("不感兴趣", key=f"{prefix}-dislike-{item['news_id']}", use_container_width=True):
            api_post("/me/feedback", {"news_id": item["news_id"], "feedback_type": "dislike"}, auth=True)
            st.rerun()
        if feedback_cols[2].button("屏蔽类别", key=f"{prefix}-block-{item['news_id']}", use_container_width=True):
            api_post(
                "/me/feedback",
                {"news_id": item["news_id"], "feedback_type": "block_category", "category": item.get("category")},
                auth=True,
            )
            st.rerun()


def show_recommendations(top_k: int) -> None:
    render_app_header("个性化新闻流", "结合点击、收藏、浏览历史、反馈和本地资料库主题生成推荐。")
    profile_col, summary_col = st.columns([2, 1])
    profile = api_get("/me/profile", auth=True)
    recommendations = api_get(f"/me/recommend?top_k={top_k}", auth=True)["items"]

    with profile_col:
        with st.container(border=True):
            st.subheader("兴趣画像")
            st.write("偏好类别：", "、".join(profile.get("preferred_categories", [])) or "暂无")
            st.write("关键词：", "、".join(profile.get("keywords", [])) or "暂无")
            st.write("近期点击：", "、".join(profile.get("recent_clicked_news", [])) or "暂无")

    with summary_col:
        with st.container(border=True):
            st.subheader("AI 画像总结")
            if st.button("生成画像总结", use_container_width=True):
                st.write(api_get("/me/profile/summary", auth=True)["summary"])

    st.subheader("推荐列表")
    for item in recommendations:
        article_card(item, "rec")


def show_article_detail() -> None:
    render_app_header("新闻详情", "查看推荐理由、AI 摘要、相关新闻，并用本地资料库解释当前新闻。")
    news_id = st.session_state.selected_news_id
    if not news_id:
        st.info("请先在推荐页、收藏页或历史页点击一篇新闻标题。")
        return

    api_post(f"/me/articles/{news_id}/view", {}, auth=True)
    detail = api_get(f"/me/articles/{news_id}", auth=True)
    article = detail["article"]

    with st.container(border=True):
        st.markdown(
            f"""
            <span class="meta-pill">{article['category']}</span>
            <span class="meta-pill">{article['subcategory']}</span>
            <span class="meta-pill">新闻 ID：{article['news_id']}</span>
            """,
            unsafe_allow_html=True,
        )
        st.subheader(article["title"])
        st.write(article.get("abstract") or "暂无摘要")
        st.info(f"推荐理由：{detail['reason']}")

        action_cols = st.columns(5)
        favorite_label = "取消收藏" if detail["favorite"] else "收藏新闻"
        if action_cols[0].button(favorite_label, use_container_width=True):
            api_post(f"/me/articles/{news_id}/favorite", {"favorite": not detail["favorite"]}, auth=True)
            st.rerun()
        if action_cols[1].button("喜欢", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "like"}, auth=True)
            st.rerun()
        if action_cols[2].button("不感兴趣", use_container_width=True):
            api_post("/me/feedback", {"news_id": news_id, "feedback_type": "dislike"}, auth=True)
            st.rerun()
        if action_cols[3].button("资料解读", use_container_width=True):
            st.session_state.last_rag_result = api_post(f"/me/articles/{news_id}/grounded-analysis", {}, auth=True)
        if article.get("url"):
            action_cols[4].link_button("查看原文", article["url"], use_container_width=True)
        else:
            action_cols[4].caption("暂无原文链接")

    if st.session_state.last_rag_result:
        result = st.session_state.last_rag_result
        with st.container(border=True):
            st.subheader("本地资料解读")
            st.write(result.get("answer", ""))
            st.caption(f"可信度：{result.get('confidence')} | 证据不足：{result.get('missing_evidence')}")
            render_citations(result.get("citations", []))
            render_trace(result.get("workflow_trace", []))

    summary_col, qa_col = st.columns([1, 1])
    with summary_col:
        with st.container(border=True):
            st.subheader("AI 新闻摘要")
            if st.button("生成摘要", use_container_width=True):
                summary = api_post(f"/me/articles/{news_id}/summary", {}, auth=True)
                st.write(summary["one_sentence"])
                for point in summary.get("key_points", []):
                    st.markdown(f"- {point}")
                st.caption(summary.get("audience", ""))

    with qa_col:
        with st.container(border=True):
            st.subheader("新闻问答")
            question = st.text_area("问题", placeholder="例如：这篇新闻和推荐系统有什么关系？")
            if st.button("提问", use_container_width=True):
                if question.strip():
                    answer = api_post(f"/me/articles/{news_id}/ask", {"question": question}, auth=True)
                    st.write(answer["answer"])
                else:
                    st.warning("请输入问题。")

    st.subheader("相关新闻")
    for related in detail.get("related", []):
        article_card(related, "related")


def show_documents() -> None:
    render_app_header("本地资料库", "上传 Markdown、TXT、PDF，系统会解析、切分、索引，并在问答和新闻解读中引用来源。")
    with st.container(border=True):
        uploaded = st.file_uploader("上传资料", type=["md", "markdown", "txt", "pdf"])
        if uploaded and st.button("写入资料库", type="primary", use_container_width=True):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
            response = httpx.post(
                f"{API_BASE_URL}/me/documents/upload",
                files=files,
                headers=auth_headers(),
                timeout=120,
            )
            if response.status_code >= 400:
                st.error(response.json().get("detail", "上传失败"))
            else:
                st.success(response.json().get("message", "上传成功"))
                st.rerun()

    documents = api_get("/me/documents", auth=True)["items"]
    if not documents:
        st.info("还没有上传资料。")
        return
    for document in documents:
        with st.container(border=True):
            st.subheader(document["filename"])
            st.write(f"状态：{document['status']} | 切片数：{document['chunk_count']} | 更新时间：{document['updated_at']}")
            if document.get("error_message"):
                st.warning(document["error_message"])
            cols = st.columns(3)
            if cols[0].button("查看切片", key=f"view-doc-{document['document_id']}", use_container_width=True):
                detail = api_get(f"/me/documents/{document['document_id']}", auth=True)
                st.json(detail.get("chunks", []))
            if cols[1].button("重新索引", key=f"reindex-doc-{document['document_id']}", use_container_width=True):
                st.write(api_post(f"/me/documents/{document['document_id']}/reindex", {}, auth=True))
                st.rerun()
            if cols[2].button("删除", key=f"delete-doc-{document['document_id']}", use_container_width=True):
                api_delete(f"/me/documents/{document['document_id']}", auth=True)
                st.rerun()


def show_rag_query() -> None:
    render_app_header("资料库问答", "只基于你上传的本地资料回答，并展示引用来源、可信度和答案评估。")
    documents = api_get("/me/documents", auth=True)["items"]
    doc_options = {"全部资料": None}
    doc_options.update({item["filename"]: item["document_id"] for item in documents})
    with st.container(border=True):
        question = st.text_area("问题", placeholder="例如：资料中如何讨论 AI 监管和推荐系统合规？")
        selected_doc = st.selectbox("检索范围", list(doc_options.keys()))
        top_k = st.slider("引用片段数量", min_value=1, max_value=10, value=5)
        if st.button("开始问答", type="primary", use_container_width=True):
            if not question.strip():
                st.warning("请输入问题。")
            else:
                st.session_state.last_rag_result = api_post(
                    "/me/rag/query",
                    {"question": question, "top_k": top_k, "document_id": doc_options[selected_doc]},
                    auth=True,
                )

    result = st.session_state.last_rag_result
    if result:
        with st.container(border=True):
            st.subheader("回答")
            st.write(result.get("answer", ""))
            st.caption(f"可信度：{result.get('confidence')} | 证据不足：{result.get('missing_evidence')}")
            st.subheader("引用来源")
            render_citations(result.get("citations", []))
            st.subheader("答案评估")
            st.json(result.get("evaluation", {}))
            render_trace(result.get("workflow_trace", []))


def show_collection(path: str, title: str, empty_message: str) -> None:
    render_app_header(title, "你的阅读行为会进入兴趣画像，帮助系统持续调整推荐结果。")
    items = api_get(path, auth=True)["items"]
    if not items:
        st.info(empty_message)
        return
    for item in items:
        article_card(item, path.replace("/", "-"))


def show_agent(top_k_default: int) -> None:
    render_app_header("多 Agent 助手", "Router、Retriever、Reranker、Answer、Verifier 协作完成推荐、资料问答和评估请求。")
    with st.container(border=True):
        query = st.text_input("输入需求", placeholder="例如：结合我上传的资料，推荐几篇 AI 监管相关的新闻")
        top_k = st.slider("返回数量", min_value=1, max_value=12, value=min(top_k_default, 8))
        if st.button("运行多 Agent", type="primary", use_container_width=True):
            if not query.strip():
                st.warning("请输入需求。")
            else:
                st.session_state.last_agent_result = api_post("/me/agent/chat", {"query": query, "top_k": top_k}, auth=True)

    result = st.session_state.last_agent_result
    if not result:
        return
    with st.container(border=True):
        st.subheader("助手回答")
        st.write(result.get("answer", ""))
        st.caption(f"识别意图：{result.get('intent')}")
        render_trace(result.get("workflow_trace", []))
        if result.get("rag", {}).get("citations"):
            st.subheader("资料引用")
            render_citations(result["rag"]["citations"])
        if result.get("items"):
            st.subheader("相关新闻")
            for item in result["items"]:
                article_card(item, "agent-chat")


def show_evaluation() -> None:
    render_app_header("评估看板", "展示推荐系统离线指标，便于对比不同推荐策略。")
    with st.container(border=True):
        k = st.slider("K", min_value=1, max_value=20, value=10)
        if st.button("运行评估", use_container_width=True):
            st.json(api_post("/evaluate", {"k": k}))


def show_app() -> None:
    top_k = sidebar()
    if st.session_state.page == "推荐":
        show_recommendations(top_k)
    elif st.session_state.page == "新闻详情":
        show_article_detail()
    elif st.session_state.page == "本地资料库":
        show_documents()
    elif st.session_state.page == "资料库问答":
        show_rag_query()
    elif st.session_state.page == "我的收藏":
        show_collection("/me/favorites", "我的收藏", "还没有收藏新闻。")
    elif st.session_state.page == "浏览历史":
        show_collection("/me/history", "浏览历史", "还没有浏览历史。")
    elif st.session_state.page == "多 Agent 助手":
        show_agent(top_k)
    elif st.session_state.page == "评估看板":
        show_evaluation()


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
    st.error(exc.response.json().get("detail", "请求失败"))
except httpx.HTTPError as exc:
    st.error(f"后端服务不可用：{exc}")
    st.code("uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
