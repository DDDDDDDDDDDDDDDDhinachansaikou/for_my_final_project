import streamlit as st
import pandas as pd
import os
import json
from google.oauth2 import service_account
import gspread
from datetime import date

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
        df = pd.DataFrame(columns=['user_id', 'password', 'available_dates'])
    return df

def save_df(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def register_user(user_id, password):
    user_id = str(user_id)
    password = str(password)
    df = get_df()
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    if user_id in df['user_id'].values:
        return False
    new_entry = pd.DataFrame([{'user_id': user_id, 'password': password, 'available_dates': ''}])
    df = pd.concat([df, new_entry], ignore_index=True)
    save_df(df)
    return True

def authenticate_user(user_id, password):
    user_id = str(user_id)
    password = str(password)
    df = get_df()
    if 'user_id' not in df.columns or 'password' not in df.columns:
        return False
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
    if 'available_dates' not in df.columns:
        return []
    matched = df[(df['available_dates'].str.contains(date, na=False)) & (df['user_id'] != current_user_id)]['user_id'].tolist()
    return matched

def show_all_users():
    st.subheader("使用者資料總覽")
    df = get_df()
    if df.empty:
        st.info("目前尚無任何註冊使用者")
    else:
        st.dataframe(df)

# Streamlit App
st.title("多人會議可用時間系統")

# 初始化 session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""
if 'page' not in st.session_state:
    st.session_state.page = "登入"

# 功能選單（無論登入與否都顯示，登入後才執行）
page_options = ["登入", "註冊"]
if st.session_state.authenticated:
    page_options = ["登記可用時間", "查詢可配對使用者", "管理介面", "登出"]

selected_page = st.sidebar.radio("選擇功能", page_options, index=page_options.index(st.session_state.page) if st.session_state.page in page_options else 0)
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
                st.experimental_rerun()
            else:
                st.error("該 ID 已存在，請使用其他名稱")
        else:
            st.warning("請填入完整資訊")

elif page == "登入":
    st.header("登入帳號")
    login_user = st.text_input("使用者 ID")
    login_pass = st.text_input("密碼", type="password")
    if st.button("登入"):
        if authenticate_user(login_user, login_pass):
            st.session_state.authenticated = True
            st.session_state.user_id = login_user
            st.session_state.page = "登記可用時間"
            st.success(f"歡迎 {login_user}，請稍候...")
            st.experimental_rerun()
        else:
            st.error("登入失敗，請重新確認帳號與密碼")

elif page == "登記可用時間" and st.session_state.authenticated:
    st.header(f"使用者 {st.session_state.user_id} 可用時間登記")
    date_range = pd.date_range(date.today(), periods=30).tolist()
    selected_dates = st.multiselect("請選擇可用日期：", date_range, format_func=lambda d: d.strftime("%Y-%m-%d"))
    date_str_list = [d.strftime("%Y-%m-%d") for d in selected_dates]
    if st.button("提交可用日期"):
        if date_str_list:
            update_availability(st.session_state.user_id, date_str_list)
        else:
            st.warning("請至少選擇一個日期")

elif page == "查詢可配對使用者" and st.session_state.authenticated:
    st.header("查詢誰在某天有空")
    query_date = st.selectbox("選擇查詢日期：", pd.date_range(date.today(), periods=30).tolist(), format_func=lambda d: d.strftime("%Y-%m-%d"))
    query_str = query_date.strftime("%Y-%m-%d")
    if st.button("查詢"):
        users = find_users_by_date(query_str, st.session_state.user_id)
        if users:
            st.info(f"在 {query_str} 有空的使用者：")
            st.write(users)
        else:
            st.warning("當天無人可配對")

elif page == "管理介面" and st.session_state.authenticated:
    show_all_users()

elif page == "登出":
    st.session_state.authenticated = False
    st.session_state.user_id = ""
    st.session_state.page = "登入"
    st.success("您已成功登出，正在跳轉...")
    st.experimental_rerun()
