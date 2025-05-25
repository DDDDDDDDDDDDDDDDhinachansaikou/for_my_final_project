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
