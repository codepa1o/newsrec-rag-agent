from __future__ import annotations

import os

import httpx
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


st.set_page_config(page_title="智能新闻推荐系统", layout="wide")
st.title("智能新闻推荐系统")
st.caption("基于用户兴趣画像、语义检索、重排序和 RAG 解释的个性化新闻推荐 Demo。")

if "token" not in st.session_state:
    st.session_state.token = ""
if "user" not in st.session_state:
    st.session_state.user = None


def auth_headers() -> dict[str, str]:
    if not st.session_state.token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_get(path: str, auth: bool = False) -> dict:
    response = httpx.get(f"{API_BASE_URL}{path}", headers=auth_headers() if auth else None, timeout=20)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, auth: bool = False) -> dict:
    response = httpx.post(f"{API_BASE_URL}{path}", json=payload, headers=auth_headers() if auth else None, timeout=20)
    response.raise_for_status()
    return response.json()


def show_auth_page() -> None:
    st.info("演示账号：用户名 U100，密码 demo123456。也可以注册一个新账号。")
    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        st.subheader("账号登录")
        username = st.text_input("用户名", value="U100", key="login-username")
        password = st.text_input("密码", value="demo123456", type="password", key="login-password")
        if st.button("登录", type="primary"):
            try:
                payload = api_post("/auth/login", {"username": username, "password": password})
                st.session_state.token = payload["token"]
                st.session_state.user = payload["user"]
                st.success("登录成功")
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "登录失败"))
            except httpx.HTTPError as exc:
                st.error(f"无法连接后端服务：{exc}")

    with register_tab:
        st.subheader("创建账号")
        new_username = st.text_input("用户名", key="register-username")
        display_name = st.text_input("昵称", key="register-display-name")
        new_password = st.text_input("密码", type="password", key="register-password")
        if st.button("注册"):
            try:
                api_post(
                    "/auth/register",
                    {"username": new_username, "password": new_password, "display_name": display_name or None},
                )
                st.success("注册成功，请回到登录页登录")
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "注册失败"))
            except httpx.HTTPError as exc:
                st.error(f"无法连接后端服务：{exc}")


def show_app() -> None:
    user = st.session_state.user or {}

    with st.sidebar:
        st.header("当前用户")
        st.write(user.get("display_name", user.get("username", "未知用户")))
        st.caption(f"用户 ID：{user.get('user_id', '-')}")
        top_k = st.slider("推荐数量", min_value=3, max_value=20, value=8)
        if st.button("退出登录"):
            try:
                api_post("/auth/logout", {}, auth=True)
            finally:
                st.session_state.token = ""
                st.session_state.user = None
                st.rerun()

    profile_col, eval_col = st.columns([2, 1])
    profile = api_get("/me/profile", auth=True)
    recommendations = api_get(f"/me/recommend?top_k={top_k}", auth=True)["items"]

    with profile_col:
        st.subheader("兴趣画像")
        st.write("偏好类别：", "、".join(profile.get("preferred_categories", [])) or "暂无")
        st.write("关键词：", "、".join(profile.get("keywords", [])) or "暂无")
        st.write("近期点击：", "、".join(profile.get("recent_clicked_news", [])) or "暂无")
        blocked = profile.get("blocked_categories", [])
        if blocked:
            st.write("已屏蔽类别：", "、".join(blocked))

    with eval_col:
        st.subheader("离线评估")
        if st.button("运行评估"):
            st.json(api_post("/evaluate", {"k": 10}))

    st.subheader("个性化新闻流")
    for item in recommendations:
        with st.container(border=True):
            st.caption(f"{item['category']} · 推荐分 {item['score']}")
            st.markdown(f"### {item['title']}")
            st.write(item["abstract"])
            st.info(item["reason"])
            feedback_cols = st.columns(3)
            if feedback_cols[0].button("喜欢", key=f"like-{item['news_id']}"):
                api_post("/me/feedback", {"news_id": item["news_id"], "feedback_type": "like"}, auth=True)
                st.rerun()
            if feedback_cols[1].button("不感兴趣", key=f"dislike-{item['news_id']}"):
                api_post("/me/feedback", {"news_id": item["news_id"], "feedback_type": "dislike"}, auth=True)
                st.rerun()
            if feedback_cols[2].button("屏蔽类别", key=f"block-{item['news_id']}"):
                api_post(
                    "/me/feedback",
                    {
                        "news_id": item["news_id"],
                        "feedback_type": "block_category",
                        "category": item["category"],
                    },
                    auth=True,
                )
                st.rerun()


try:
    if st.session_state.token:
        show_app()
    else:
        show_auth_page()
except httpx.HTTPError as exc:
    st.error(f"后端服务不可用：{exc}")
    st.code("uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
