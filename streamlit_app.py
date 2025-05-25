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
try:
    sheet = client.open(SHEET_NAME).sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"找不到名為 `{SHEET_NAME}` 的 Google Sheets 文件，請確認名稱是否正確")
    st.stop()
except gspread.exceptions.APIError as e:
    st.error(f"Google Sheets API 錯誤：{e}")
    st.stop()

@st.cache_data(ttl=60)
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
        df = df.fillna("")
    return df

def save_df(df):
    df = df.fillna("")
    
    # 確保所有欄位都存在且順序一致
    expected_cols = ['user_id', 'password', 'available_dates', 'friends', 'friend_requests']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    df = df[expected_cols]  # 強制按照正確順序排序欄位

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
    df = get_df()
    match = df[(df['user_id'] == str(user_id)) & (df['password'] == str(password))]
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
    st.dataframe(df)


# 儲存每位用戶的上次送出好友申請的時間（session 範圍）
if "friend_request_timestamps" not in st.session_state:
    st.session_state.friend_request_timestamps = {}

def send_friend_request(current_user, target_user):
    if current_user == target_user:
        st.warning("不能對自己發送好友申請")
        return

    df = get_df()

    if target_user not in df['user_id'].values:
        st.error("使用者不存在")
        return

    # 檢查是否為好友
    curr_friends = df.loc[df['user_id'] == current_user, 'friends'].values[0]
    curr_friends_set = set(curr_friends.split(',')) if curr_friends else set()
    if target_user in curr_friends_set:
        st.info("你們已經是好友")
        return

    # 檢查是否已收到對方的申請
    curr_requests = df.loc[df['user_id'] == current_user, 'friend_requests'].values[0]
    curr_requests_set = set(curr_requests.split(',')) if curr_requests else set()
    if target_user in curr_requests_set:
        st.info(f"{target_user} 已經對你發送好友申請，請回應")
        return

    # 檢查是否已發送過
    target_requests = df.loc[df['user_id'] == target_user, 'friend_requests'].values[0]
    target_requests_set = set(target_requests.split(',')) if target_requests else set()
    if current_user in target_requests_set:
        st.info("已發送好友申請，請等待對方回應")
        return

    # 防止 bouncing - 緩衝 1 秒
    now = time.time()
    last_sent = st.session_state.friend_request_timestamps.get(target_user, 0)
    if now - last_sent < 1:
        st.warning("您剛剛才發送過申請，請稍候再試")
        return

    # 發送好友申請
    target_requests_set.add(current_user)
    df.loc[df['user_id'] == target_user, 'friend_requests'] = ','.join(target_requests_set)

    save_df(df)
    st.cache_data.clear()

    st.session_state.friend_request_timestamps[target_user] = now
    st.success("好友申請已送出")

def respond_to_requests(user_id):
    df = get_df()
    idx = df[df['user_id'] == user_id].index[0]

    requests_raw = df.at[idx, 'friend_requests']
    requests = list(filter(None, requests_raw.split(',')))

    if not requests:
        st.info("目前沒有好友申請")
        return

    existing_friends = set(filter(None, df.at[idx, 'friends'].split(',')))

    for requester in requests:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write(f"來自 **{requester}** 的好友申請")
        with col2:
            accept_key = f"accept_{requester}_{user_id}"
            reject_key = f"reject_{requester}_{user_id}"
            if st.button("接受", key=accept_key):
                # 加入彼此為好友
                existing_friends.add(requester)
                df.at[idx, 'friends'] = ','.join(existing_friends)

                r_idx = df[df['user_id'] == requester].index[0]
                requester_friends = set(filter(None, df.at[r_idx, 'friends'].split(',')))
                requester_friends.add(user_id)
                df.at[r_idx, 'friends'] = ','.join(requester_friends)

                # 移除該好友申請
                updated_requests = [r for r in requests if r != requester]
                df.at[idx, 'friend_requests'] = ','.join(updated_requests)

                save_df(df)
                st.success(f"您已與 {requester} 成為好友")
                st.rerun()

            elif st.button("拒絕", key=reject_key):
                # 移除該好友申請
                updated_requests = [r for r in requests if r != requester]
                df.at[idx, 'friend_requests'] = ','.join(updated_requests)

                save_df(df)
                st.info(f"已拒絕 {requester} 的好友申請")
                st.rerun()

def show_friends_availability(user_id):
    df = get_df()
    idx = df[df['user_id'] == user_id].index[0]
    friends = df.at[idx, 'friends']
    friends = list(filter(None, friends.split(',')))
    if not friends:
        st.info("目前尚無好友")
        return

    st.subheader("好友的空閒日期")
    for friend in friends:
        friend_data = df[df['user_id'] == friend]
        if not friend_data.empty:
            dates = friend_data.iloc[0]['available_dates']
            date_list = dates.split(',') if dates else []
            st.markdown(f"**{friend}**: {'、'.join(date_list) if date_list else '尚未登記'}")

st.title("多人會議可用時間系統")

# 初始化 session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""
if 'page' not in st.session_state:
    st.session_state.page = "登入"
if 'remember_me' not in st.session_state:
    st.session_state.remember_me = False
if 'rerun_triggered' not in st.session_state:
    st.session_state.rerun_triggered = False

# URL query-based page control
query_page = st.query_params.get("page")
if query_page and st.session_state.page != query_page:
    st.session_state.page = query_page

# 自動跳轉處理
if st.session_state.page == "登入成功" and not st.session_state.rerun_triggered:
    st.session_state.page = "登記可用時間"
    st.query_params["page"] = "登記可用時間"
    st.session_state.rerun_triggered = True
    st.rerun()
elif st.session_state.page == "登出完成" and not st.session_state.rerun_triggered:
    st.session_state.page = "登入"
    st.query_params["page"] = "登入"
    st.session_state.rerun_triggered = True
    st.rerun()

# 功能選單
page_options = ["登入", "註冊"]
if st.session_state.authenticated:
    page_options = ["登記可用時間", "查詢可配對使用者"]
    if st.session_state.user_id == "GM":
        page_options.append("管理介面")
    page_options.append("登出")

selected_page = st.sidebar.radio("選擇功能", page_options, index=page_options.index(st.session_state.page) if st.session_state.page in page_options else 0)
st.session_state.page = selected_page
page = selected_page

if page == "註冊":
    st.header("註冊帳號")
    new_user = st.text_input("請輸入新使用者 ID")
    new_pass = st.text_input("請輸入密碼", type="password")
    if st.button("註冊"):
        if new_user and new_pass:
            if register_user(new_user, new_pass):
                st.success("註冊成功！請前往登入頁面")
                st.session_state.page = "登入"
                st.query_params["page"] = "登入"
                st.session_state.rerun_triggered = False
                st.rerun()
        else:
            st.warning("請填入完整資訊")

elif page == "登入":
    st.header("登入帳號")
    login_user = st.text_input("使用者 ID")
    login_pass = st.text_input("密碼", type="password")
    remember = st.checkbox("記住我")
    if st.button("登入"):
        if authenticate_user(login_user, login_pass):
            st.session_state.authenticated = True
            st.session_state.user_id = login_user
            st.session_state.remember_me = remember
            st.success(f"歡迎 {login_user}，已成功登入。")
            st.session_state.page = "登入成功"
            st.session_state.rerun_triggered = False
            st.rerun()
        else:
            st.error("登入失敗，請重新確認帳號與密碼")

elif page == "登記可用時間" and st.session_state.authenticated:
    st.header(f"使用者 {st.session_state.user_id} 可用時間登記")
    date_range = pd.date_range(date.today(), periods=30).tolist()
    selected_dates = st.multiselect("請選擇可用日期：", date_range, format_func=lambda d: d.strftime("%Y-%m-%d"))
    if st.button("更新可用日期"):
        selected_strs = [d.strftime("%Y-%m-%d") for d in selected_dates]
        update_availability(st.session_state.user_id, selected_strs)

elif page == "查詢可配對使用者" and st.session_state.authenticated:
    st.header("查詢誰在某天有空")
    date_range = pd.date_range(date.today(), periods=30).tolist()
    query_dates = st.multiselect("選擇查詢日期：", date_range, format_func=lambda d: d.strftime("%Y-%m-%d"))
    query_strs = [d.strftime("%Y-%m-%d") for d in query_dates]
    if st.button("查詢"):
        any_found = False
        for q in query_strs:
            users = find_users_by_date(q, st.session_state.user_id)
            if users:
                any_found = True
                st.markdown(f"### {q} 有空的使用者：")
                for user in users:
                    st.markdown(f"- {user}")
        if not any_found:
            st.warning("所選日期中無人可配對")

elif page == "管理介面" and st.session_state.authenticated and st.session_state.user_id == "GM":
    show_all_users()

elif page == "登出":
    st.session_state.authenticated = False
    st.session_state.user_id = ""
    st.session_state.remember_me = False
    st.success("您已成功登出。")
    st.session_state.page = "登出完成"
    st.session_state.rerun_triggered = False
    st.rerun()

if st.session_state.get("authenticated"):
    st.sidebar.subheader("好友功能")
    with st.sidebar.expander("送出好友申請"):
        target = st.text_input("輸入對方 ID", key="apply_friend")
        if st.button("送出好友申請"):
            send_friend_request(st.session_state.user_id, target)
    with st.sidebar.expander("回應好友申請"):
        respond_to_requests(st.session_state.user_id)
    with st.sidebar.expander("查看好友空閒時間"):
        show_friends_availability(st.session_state.user_id)
