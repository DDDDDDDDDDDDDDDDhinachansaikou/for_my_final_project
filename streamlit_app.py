import streamlit as st
import pandas as pd
import os
import json
from google.oauth2 import service_account
import gspread
from datetime import date

# === 使用 Streamlit Secrets 讀取 Google Sheets 金鑰 ===
secrets = st.secrets["gspread"]
credentials = service_account.Credentials.from_service_account_info(secrets)

# === 連接 Google Sheets ===
SHEET_NAME = 'meeting_records'
client = gspread.authorize(credentials)
sheet = client.open(SHEET_NAME).sheet1

# === 資料存取函數 ===
def get_df():
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def save_df(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def register_user(user_id, password):
    df = get_df()
    if user_id in df['user_id'].values:
        return False
    new_entry = pd.DataFrame([{'user_id': user_id, 'password': password, 'available_dates': ''}])
    df = pd.concat([df, new_entry], ignore_index=True)
    save_df(df)
    return True

def authenticate_user(user_id, password):
    df = get_df()
    match = df[(df['user_id'] == user_id) & (df['password'] == password)]
    return not match.empty

def update_availability(user_id, available_dates):
    df = get_df()
    date_str = ','.join(available_dates)
    df.loc[df['user_id'] == user_id, 'available_dates'] = date_str
    save_df(df)
    st.success(f"✅ 使用者 {user_id} 的可用日期已更新為：{date_str}")

def find_users_by_date(date):
    df = get_df()
    matched = df[df['available_dates'].str.contains(date, na=False)]['user_id'].tolist()
    return matched

# Streamlit App
st.title("📅 可揪時間系統")

page = st.sidebar.selectbox("選擇功能", ["註冊", "登入並登記時間", "查詢可配對使用者"])

if page == "註冊":
    st.header("🔑 註冊帳號")
    new_user = st.text_input("請輸入新使用者 ID")
    new_pass = st.text_input("請輸入密碼", type="password")
    if st.button("註冊"):
        if new_user and new_pass:
            if register_user(new_user, new_pass):
                st.success("🎉 註冊成功！請前往登入頁面")
            else:
                st.error("⚠️ 該 ID 已存在，請使用其他名稱")
        else:
            st.warning("請填入完整資訊")

elif page == "登入並登記時間":
    st.header("🔐 登入帳號")
    login_user = st.text_input("使用者 ID")
    login_pass = st.text_input("密碼", type="password")
    if st.button("登入"):
        if authenticate_user(login_user, login_pass):
            st.success(f"🚀 歡迎 {login_user}，請選擇你的可用日期：")
            selected_dates = st.multiselect("點選可用日期", options=pd.date_range(start=date.today(), periods=60).strftime('%Y-%m-%d').tolist())
            if st.button("提交可用日期"):
                update_availability(login_user, selected_dates)
        else:
            st.error("⚠️ 登入失敗，請重新確認帳號與密碼")

elif page == "查詢可配對使用者":
    st.header("🔍 查詢誰在某天有空")
    selected_day = st.date_input("請選擇查詢日期", value=date.today())
    query_str = selected_day.strftime('%Y-%m-%d')
    if st.button("查詢"):
        users = find_users_by_date(query_str)
        if users:
            st.info(f"在 {query_str} 有空的使用者：")
            st.write(users)
        else:
            st.warning("當天無人可配對")
