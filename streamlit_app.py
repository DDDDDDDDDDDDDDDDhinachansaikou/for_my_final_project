import streamlit as st
import pandas as pd
import os
import json
from google.oauth2 import service_account
import gspread

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
    # 如果表格是空的，初始化欄位
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

def find_users_by_date(date):
    df = get_df()
    if 'available_dates' not in df.columns:
        return []
    matched = df[df['available_dates'].str.contains(date, na=False)]['user_id'].tolist()
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

# 預設頁面為登入，並提供註冊與管理功能
page = st.sidebar.radio("選擇功能", ["登入", "註冊", "查詢可配對使用者", "管理介面"])

if page == "註冊":
    st.header("註冊帳號")
    new_user = st.text_input("請輸入新使用者 ID")
    new_pass = st.text_input("請輸入密碼", type="password")
    if st.button("註冊"):
        if new_user and new_pass:
            if register_user(new_user, new_pass):
                st.success("註冊成功！請前往登入頁面")
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
            st.success(f"歡迎 {login_user}，請輸入你的可用日期：")
            dates = st.text_input("可用日期（以逗號分隔）")
            if st.button("提交可用日期"):
                date_list = [d.strip() for d in dates.split(',') if d.strip()]
                update_availability(login_user, date_list)
        else:
            st.error("登入失敗，請重新確認帳號與密碼")

elif page == "查詢可配對使用者":
    st.header("查詢誰在某天有空")
    date = st.text_input("查詢日期（格式：2025-06-01）")
    if st.button("查詢"):
        if date:
            users = find_users_by_date(date)
            if users:
                st.info(f"在 {date} 有空的使用者：")
                st.write(users)
            else:
                st.warning("當天無人可配對")
        else:
            st.warning("請輸入查詢日期")

elif page == "管理介面":
    show_all_users()
