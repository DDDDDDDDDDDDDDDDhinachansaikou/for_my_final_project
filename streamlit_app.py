import streamlit as st
import pandas as pd
import os
import json
from google.oauth2 import service_account
import gspread
from datetime import date
import time
import re

# 使用 Streamlit Secrets 讀取 Google Sheets 金鑰
secrets = st.secrets["gspread"]
credentials = service_account.Credentials.from_service_account_info(secrets)

# 指定必要 scope
scoped_credentials = credentials.with_scopes([
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

# 連接 Google Sheets
SHEET_NAME = 'meeting_records'
client = gspread.authorize(scoped_credentials)
sheet = client.open(SHEET_NAME).sheet1

# 資料存取函數
def get_df():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=['user_id', 'password', 'available_dates', 'friends', 'friend_requests'])
    else:
        for col in ['user_id', 'password', 'available_dates', 'friends', 'friend_requests']:
            if col not in df.columns:
                df[col] = ''
        df['user_id'] = df['user_id'].astype(str)
        df['password'] = df['password'].astype(str)
    return df

def save_df(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def register_user(user_id, password):
    user_id = str(user_id)
    password = str(password)
    if len(password) < 6 or not re.search(r'[A-Za-z]', password):
        st.warning("密碼必須至少 6 個字元，且包含至少一個英文字母")
        return False
    df = get_df()
    if user_id in df['user_id'].values:
        return False
    new_entry = pd.DataFrame([{
        'user_id': user_id,
        'password': password,
        'available_dates': '',
        'friends': '',
        'friend_requests': ''
    }])
    df = pd.concat([df, new_entry], ignore_index=True)
    save_df(df)
    return True

def authenticate_user(user_id, password):
    user_id = str(user_id)
    password = str(password)
    df = get_df()
    match = df[(df['user_id'] == user_id) & (df['password'] == password)]
    return not match.empty

def update_availability(user_id, available_dates):
    df = get_df()
    date_str = ','.join(available_dates)
    df.loc[df['user_id'] == user_id, 'available_dates'] = date_str
    save_df(df)
    st.success(f"使用者 {user_id} 的可用日期已更新為：{date_str}")

def find_users_by_date(date, current_user_id):
    df = get_df()
    matched = df[(df['available_dates'].str.contains(date, na=False)) & (df['user_id'] != current_user_id)]['user_id'].tolist()
    return matched

def show_all_users():
    st.subheader("使用者資料總覽")
    df = get_df()
    if df.empty:
        st.info("目前尚無任何註冊使用者")
    else:
        st.dataframe(df)

def send_friend_request(from_user, to_user):
    df = get_df()
    if to_user not in df['user_id'].values:
        st.error("此使用者不存在")
        return
    to_index = df[df['user_id'] == to_user].index[0]
    requests = df.at[to_index, 'friend_requests'].split(',') if df.at[to_index, 'friend_requests'] else []
    if from_user not in requests:
        requests.append(from_user)
    df.at[to_index, 'friend_requests'] = ','.join([r for r in requests if r])
    save_df(df)
    st.success("好友申請已送出")

def respond_to_friend_request(user_id, requester, accept):
    df = get_df()
    user_index = df[df['user_id'] == user_id].index[0]
    req_index = df[df['user_id'] == requester].index[0]
    requests = df.at[user_index, 'friend_requests'].split(',') if df.at[user_index, 'friend_requests'] else []
    requests = [r for r in requests if r != requester]
    df.at[user_index, 'friend_requests'] = ','.join(requests)
    if accept:
        for u, i in [(user_id, req_index), (requester, user_index)]:
            friends = df.at[i, 'friends'].split(',') if df.at[i, 'friends'] else []
            if u not in friends:
                friends.append(u)
            df.at[i, 'friends'] = ','.join([f for f in friends if f])
    save_df(df)
    st.success("已更新好友狀態")

def get_friends(user_id):
    df = get_df()
    row = df[df['user_id'] == user_id]
    if not row.empty:
        return row.iloc[0]['friends'].split(',') if row.iloc[0]['friends'] else []
    return []

def get_friend_requests(user_id):
    df = get_df()
    row = df[df['user_id'] == user_id]
    if not row.empty:
        return row.iloc[0]['friend_requests'].split(',') if row.iloc[0]['friend_requests'] else []
    return []

# 初始化狀態
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""
if 'page_marker' not in st.session_state:
    st.session_state.page_marker = st.query_params.get("page", ["登入"])[0]

# 導航函數（只透過 query param 控制頁面）
def navigate_to(page):
    st.query_params["page"] = page
    st.rerun()

# 頁面同步
query_page = st.query_params.get("page", ["登入"])[0]
if st.session_state.page_marker != query_page:
    st.session_state.page_marker = query_page

# 側邊欄頁面選單
if st.session_state.authenticated:
    pages = ["登記可用時間", "查詢可配對使用者", "好友管理"]
    if st.session_state.user_id == "GM":
        pages.append("管理介面")
    pages.append("登出")
else:
    pages = ["登入", "註冊"]

current_page = st.session_state.page_marker if st.session_state.page_marker in pages else pages[0]
st.sidebar.radio("選擇功能", pages, index=pages.index(current_page), key="page")

# 頁面功能整合
if current_page == "註冊":
    st.header("註冊帳號")
    new_user = st.text_input("新使用者 ID")
    new_pass = st.text_input("密碼", type="password")
    if st.button("註冊"):
        if new_user and new_pass:
            if register_user(new_user, new_pass):
                st.success("註冊成功！請前往登入頁面")
                navigate_to("登入")
            else:
                st.warning("使用者已存在或密碼不合規")

elif current_page == "登入":
    st.header("登入帳號")
    login_user = st.text_input("使用者 ID")
    login_pass = st.text_input("密碼", type="password")
    if st.button("登入"):
        if authenticate_user(login_user, login_pass):
            st.session_state.authenticated = True
            st.session_state.user_id = login_user
            st.success(f"歡迎 {login_user}，已成功登入。")
            navigate_to("登記可用時間")
        else:
            st.error("帳號或密碼錯誤")

elif current_page == "登記可用時間" and st.session_state.authenticated:
    st.header("登記可用時間")
    date_range = pd.date_range(date.today(), periods=30).tolist()
    selected_dates = st.multiselect("選擇可用日期", date_range, format_func=lambda d: d.strftime("%Y-%m-%d"))
    if st.button("更新可用日期"):
        selected_strs = [d.strftime("%Y-%m-%d") for d in selected_dates]
        update_availability(st.session_state.user_id, selected_strs)

elif current_page == "查詢可配對使用者" and st.session_state.authenticated:
    st.header("查詢可配對使用者")
    date_range = pd.date_range(date.today(), periods=30).tolist()
    query_dates = st.multiselect("選擇查詢日期", date_range, format_func=lambda d: d.strftime("%Y-%m-%d"))
    if st.button("查詢"):
        df = get_df()
        results = {}
        for d in query_dates:
            date_str = d.strftime("%Y-%m-%d")
            users = find_users_by_date(date_str, st.session_state.user_id)
            if users:
                results[date_str] = users
        if results:
            for d, users in results.items():
                st.markdown(f"### {d}")
                for u in users:
                    st.markdown(f"- {u}")
        else:
            st.warning("選擇日期中無配對使用者")

elif current_page == "管理介面" and st.session_state.user_id == "GM":
    show_all_users()

elif current_page == "登出":
    st.session_state.authenticated = False
    st.session_state.user_id = ""
    navigate_to("登入")

if current_page == "好友管理" and st.session_state.authenticated:
    st.header("好友管理")

    st.subheader("目前好友")
    friends = get_friends(st.session_state.user_id)
    if friends:
        st.markdown(", ".join(friends))
    else:
        st.info("目前尚無好友")

    st.subheader("發送好友申請")
    to_user = st.text_input("輸入要加為好友的使用者 ID")
    if st.button("送出好友申請"):
        if to_user != st.session_state.user_id:
            send_friend_request(st.session_state.user_id, to_user)
        else:
            st.warning("不能加自己為好友")

    st.subheader("收到的好友申請")
    requests = get_friend_requests(st.session_state.user_id)
    if requests:
        for r in requests:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"好友申請來自：**{r}**")
            with col2:
                if st.button(f"接受_{r}"):
                    respond_to_friend_request(st.session_state.user_id, r, True)
                    st.rerun()
                if st.button(f"拒絕_{r}"):
                    respond_to_friend_request(st.session_state.user_id, r, False)
                    st.rerun()
    else:
        st.info("目前無收到好友申請")

    st.subheader("查詢好友的可用時間")
    if friends:
        selected_friend = st.selectbox("選擇好友", friends)
        df = get_df()
        row = df[df['user_id'] == selected_friend]
        if not row.empty:
            dates = row.iloc[0]['available_dates']
            st.markdown(f"**{selected_friend}** 的可用時間為：\n{dates}")
    else:
        st
