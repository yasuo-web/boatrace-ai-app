from datetime import datetime
import pickle
import numpy as np
import pandas as pd
from scraper import create_features, get_odds_data, get_race_data
import streamlit as st

st.set_page_config(page_title="MYAI_BOATRACE", layout="wide")

# ヘッダーエリア
st.title("🚤 MYAI_BOATRACE")

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

FEATURE_COLS = [
    "boat_number",
    "rank_score",
    "national_win_rate",
    "local_win_rate",
    "motor_2in_rate",
    "exhibit_time",
    "f_count",
    "avg_st",
    "entry_course",
    "is_course_1",
    "course_changed",
    "ex_time_rel",
    "st_rel",
    "kadomakuri_threat",
    "outer_follow_advantage",
]


@st.cache_resource
def load_model():
  with open("boat_model.pkl", "rb") as f:
    return pickle.load(f)


model = load_model()


def calculate_trifecta_probs(p):
  """全120通りの3連単確率を計算"""
  p = np.array(p)
  p = p / np.sum(p)
  n = len(p)
  trifecta = {}

  for i in range(n):
    for j in range(n):
      if i == j:
        continue
      p_i_j = p[i] * (p[j] / (1 - p[i]))
      for k in range(n):
        if k == i or k == j:
          continue
        p_i_j_k = p_i_j * (p[k] / (1 - p[i] - p[j]))
        combo = f"{i+1}-{j+1}-{k+1}"
        trifecta[combo] = p_i_j_k * 100

  return trifecta


# --- タイトル直下の操作エリア ---
st.write("---")

# 4列レイアウト（開催会場 / レース番号 / ボタン / 余白調整）
col_place, col_race, col_btn, _ = st.columns([2, 2, 2, 4])

with col_place:
  selected_place = st.selectbox("開催会場", list(JCD_MAP.keys()))

with col_race:
  # 1R〜12Rのプルダウン選択式
  race_options = [f"{i}R" for i in range(1, 13)]
  selected_race_str = st.selectbox("対象レース", race_options)
  selected_rno = int(selected_race_str.replace("R", ""))

with col_btn:
  st.write("")  # 高さ（ラベル分）の調整
  st.write("")
  submit_btn = st.button(
      "🎯 決定（予想実行）", type="primary", use_container_width=True
  )

st.write("---")

# 日付はアプリ起動日の当日（YYYYMMDD形式）に固定
today_dt = datetime.now()
date_str = today_dt.strftime("%Y%m%d")
jcd = JCD_MAP[selected_place]

# 決定ボタンが押された時の処理
if submit_btn:
  st.caption(
      f"対象日: {today_dt.strftime('%Y年%m月%d日')} | 会場: {selected_place} |"
      f" レース: {selected_rno}R"
  )

  with st.spinner(
      f"{selected_place} {selected_rno}R の最新データ・オッズを取得中..."
  ):
    # 1. データ取得
    df_raw = get_race_data(jcd, selected_rno, date_str)
    odds_dict = get_odds_data(jcd, selected_rno, date_str)

    if df_raw is None or df_raw.empty:
      st.error(
          "レースデータの取得に失敗しました。本日開催されていないか、データがまだ更新されていない可能性があります。"
      )
    else:
      # 2. AI確率計算
      df_features = create_features(df_raw)
      probs = model.predict_proba(df_features[FEATURE_COLS])[:, 1]
      trifecta_probs = calculate_trifecta_probs(probs)

      # 3. オッズ情報と結合して「期待値」を算出
      predictions = []
      for combo, ai_prob in trifecta_probs.items():
        odds = odds_dict.get(combo, 10.0)  # オッズ未取得時は10.0倍仮定
        ev = (ai_prob / 100) * odds  # 期待値 = AI確率 × オッズ

        predictions.append({
            "買い目 (3連単)": combo,
            "AI予測確率 (%)": round(ai_prob, 1),
            "オッズ": f"{odds:.1f}倍",
            "AI期待値": round(ev, 2),
        })

      # 4. 期待値の高い順にソートし、上位5点のみを抽出
      df_top5 = (
          pd.DataFrame(predictions)
          .sort_values(by="AI期待値", ascending=False)
          .head(5)
      )

      # 5. 結果表示
      st.toast("✅ 予想結果を出力しました！", icon="🎉")
      st.subheader(
          f"🏆 {selected_place} {selected_rno}R AI厳選買い目（上位5点）"
      )

      # 強調カード表示（上段）
      cols = st.columns(5)
      for idx, (_, row) in enumerate(df_top5.iterrows()):
        with cols[idx]:
          st.metric(
              label=f"第{idx+1}推奨",
              value=row["買い目 (3連単)"],
              delta=f"{row['オッズ']} / 期待値:{row['AI期待値']}",
          )

      st.write("")

      # テーブル表示（下段）
      st.dataframe(df_top5, hide_index=True, use_container_width=True)