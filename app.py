import pickle
import numpy as np
import pandas as pd
from scraper import create_features, get_race_data
import streamlit as st

st.set_page_config(page_title="AI競艇予想 Webアプリ", layout="wide")
st.title("🚤 AI競艇予想 Webアプリ（特徴量拡張版）")


@st.cache_resource
def load_model():
  with open("boat_model.pkl", "rb") as f:
    return pickle.load(f)


model = load_model()

JCD_MAP = {
    "桐生": "01",
    "戸田": "02",
    "江戸川": "03",
    "平和島": "04",
    "多摩川": "05",
    "浜名湖": "06",
    "蒲郡": "07",
    "常滑": "08",
    "津": "09",
    "三国": "10",
    "びわこ": "11",
    "住之江": "12",
    "尼崎": "13",
    "鳴門": "14",
    "丸亀": "15",
    "児島": "16",
    "宮島": "17",
    "徳山": "18",
    "下関": "19",
    "若松": "20",
    "芦屋": "21",
    "福岡": "22",
    "唐津": "23",
    "大村": "24",
}

st.sidebar.header("📌 レース選択")
selected_place = st.sidebar.selectbox("開催場", list(JCD_MAP.keys()))
selected_rno = st.sidebar.slider("レース番号", 1, 12, 1)
selected_date = st.sidebar.date_input("日付")

date_str = selected_date.strftime("%Y%m%d")
jcd = JCD_MAP[selected_place]

if st.sidebar.button("出走表を自動取得"):
  with st.spinner("BOAT RACE公式サイトからデータ取得中..."):
    df_fetched = get_race_data(jcd, selected_rno, date_str)
    if df_fetched is not None and not df_fetched.empty:
      st.session_state["race_df"] = df_fetched
      st.success("取得完了しました！")
    else:
      st.error("データの取得に失敗しました。")

if "race_df" in st.session_state:
  df_raw = st.session_state["race_df"]
  st.subheader(
      f"📋 {selected_place} {selected_rno}R 出走表データ（生データ）"
  )
  st.dataframe(df_raw, use_container_width=True)

  if st.button("AIで勝率を予想する", type="primary"):
    # 推論直前に特徴量生成エンジンを通す
    df_features = create_features(df_raw)

    feature_cols = [
        "boat_number",
        "national_win_rate",
        "local_win_rate",
        "motor_2in_rate",
        "exhibit_time",
        "is_boat_1",
        "has_flying",
        "boat1_and_flying",
        "ex_time_rel",
        "st_rel",
    ]

    probs = model.predict_proba(df_features[feature_cols])[:, 1]
    norm_probs = (probs / np.sum(probs)) * 100

    df_result = pd.DataFrame({
        "艇番": [f"{i}号艇" for i in range(1, 7)],
        "予想勝利確率 (%)": np.round(norm_probs, 1),
    }).sort_values(by="予想勝利確率 (%)", ascending=False)

    st.subheader("🎯 予想結果")
    st.dataframe(df_result, hide_index=True, use_container_width=True)