from datetime import datetime
import pickle
import random
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from scraper import (
    create_features,
    get_active_places,
    get_odds_data,
    get_purchasable_races,
    get_race_data,
)
import streamlit as st

st.set_page_config(page_title="MYAI_BOATRACE", layout="wide")


# --- キャッシュ定義（自動スピナー非表示設定） ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_active_places_cached(date_str: str):
  return get_active_places(date_str)


# --- ヘッダーエリア ---
col_title, col_reload = st.columns([4, 1])

with col_title:
  st.title("🚤 MYAI_BOATRACE")

with col_reload:
  st.write("")  # 垂直位置調整
  if st.button("🔄 最新情報に更新", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 日本時間（Asia/Tokyo）の取得と表示フォーマット設定
jst = ZoneInfo("Asia/Tokyo")
now_jst = datetime.now(jst)
date_str = now_jst.strftime("%Y%m%d")

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
weekday_str = WEEKDAYS_JP[now_jst.weekday()]
formatted_datetime = (
    f"{now_jst.strftime('%Y年%m月%d日')} ({weekday_str}) "
    f"{now_jst.strftime('%H:%M')}"
)

st.caption(formatted_datetime)

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
  try:
    with open("boat_model.pkl", "rb") as f:
      return pickle.load(f)
  except Exception:
    return None


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


def generate_sample_predictions():
  """非開催時確認用のダミー予測データ生成"""
  combos = []
  for i in range(1, 7):
    for j in range(1, 7):
      if i == j:
        continue
      for k in range(1, 7):
        if k == i or k == j:
          continue
        combos.append(f"{i}-{j}-{k}")

  predictions = []
  for combo in combos:
    if combo.startswith("1-"):
      ai_prob = round(random.uniform(2.0, 15.0), 1)
      odds = round(random.uniform(6.0, 45.0), 1)
    elif combo.startswith("2-") or combo.startswith("3-"):
      ai_prob = round(random.uniform(0.5, 5.0), 1)
      odds = round(random.uniform(30.0, 120.0), 1)
    else:
      ai_prob = round(random.uniform(0.05, 1.2), 2)
      odds = round(random.uniform(100.0, 450.0), 1)

    ev = round((ai_prob / 100) * odds, 2)
    predictions.append({
        "買い目 (3連単)": combo,
        "AI予測確率 (%)": ai_prob,
        "オッズ_num": odds,
        "オッズ": f"{odds:.1f}倍",
        "AI期待値": ev,
    })
  return pd.DataFrame(predictions)


# --- 本日開催会場の動的取得 ---
with st.spinner("現在開催中の会場を取得中..."):
  active_places = fetch_active_places_cached(date_str)

st.write("---")

# 動作確認用サンプルモード切替
use_sample = st.checkbox(
    "🧪 サンプルデータで表示結果を確認する（夜間・非開催時用）"
)

if not active_places and not use_sample:
  st.warning(
      "現在開催中の会場がないか、本日のレース日程が終了している可能性があります。"
      "（※表示確認は上の「サンプルデータで表示結果を確認する」をチェックしてください）"
  )
else:
  col_place, col_race, col_btn, _ = st.columns([2, 2, 2, 4])

  if use_sample:
    display_place_name = "住之江 [サンプル]"
    display_race_no = 12
    with col_place:
      st.selectbox("開催会場", [display_place_name], disabled=True)
    with col_race:
      st.selectbox("対象レース", ["12R"], disabled=True)
    with col_btn:
      st.write("")
      st.write("")
      submit_btn = st.button(
          "🎯 決定（予想実行）", type="primary", use_container_width=True
      )
  else:
    with col_place:
      selected_place = st.selectbox("開催会場", list(active_places.keys()))
      jcd = active_places[selected_place]

    purchasable_races = get_purchasable_races(jcd, date_str)

    with col_race:
      if not purchasable_races:
        st.selectbox("対象レース", ["本日全レース終了"], disabled=True)
        selected_rno = None
      else:
        race_options = [f"{r}R" for r in purchasable_races]
        selected_race_str = st.selectbox("対象レース", race_options)
        selected_rno = int(selected_race_str.replace("R", ""))

    with col_btn:
      st.write("")
      st.write("")
      submit_btn = st.button(
          "🎯 決定（予想実行）",
          type="primary",
          use_container_width=True,
          disabled=(selected_rno is None),
      )
    display_place_name = selected_place if "selected_place" in locals() else ""
    display_race_no = selected_rno if "selected_rno" in locals() else None

  st.write("---")

  if submit_btn:
    if use_sample:
      df_all = generate_sample_predictions()
    else:
      with st.spinner(
          f"{display_place_name} {display_race_no}R の最新データ・オッズを取得中..."
      ):
        df_raw = get_race_data(jcd, display_race_no, date_str)
        odds_dict = get_odds_data(jcd, display_race_no, date_str)

        if df_raw is None or df_raw.empty:
          st.error(
              "レースデータの取得に失敗しました。直前データ更新前などの可能性があります。"
          )
          df_all = None
        else:
          df_features = create_features(df_raw)
          probs = (
              model.predict_proba(df_features[FEATURE_COLS])[:, 1]
              if model
              else [0.3, 0.2, 0.2, 0.1, 0.1, 0.1]
          )
          trifecta_probs = calculate_trifecta_probs(probs)

          predictions = []
          for combo, ai_prob in trifecta_probs.items():
            odds = odds_dict.get(combo, 10.0)
            ev = (ai_prob / 100) * odds

            predictions.append({
                "買い目 (3連単)": combo,
                "AI予測確率 (%)": round(ai_prob, 1),
                "オッズ_num": odds,
                "オッズ": f"{odds:.1f}倍",
                "AI期待値": round(ev, 2),
            })

          df_all = pd.DataFrame(predictions)

    if df_all is not None:
      # 1. 通常の期待値上位5点
      df_top5 = df_all.sort_values(by="AI期待値", ascending=False).head(5)

      st.toast("✅ 予想結果を出力しました！", icon="🎉")
      st.subheader(
          f"🏆 {display_place_name} {display_race_no}R AI厳選買い目（上位5点）"
      )

      cols = st.columns(5)
      for idx, (_, row) in enumerate(df_top5.iterrows()):
        with cols[idx]:
          st.metric(
              label=f"第{idx+1}推奨",
              value=row["買い目 (3連単)"],
              delta=f"{row['オッズ']} / 期待値:{row['AI期待値']}",
          )

      st.write("")
      st.dataframe(
          df_top5.drop(columns=["オッズ_num"]),
          hide_index=True,
          use_container_width=True,
      )

      st.write("---")

      # 2. オッズ100倍以上の大穴予想（期待値上位1つ、ランダム1つ、理論（確率）上位1つ）
      st.subheader("💥 万舟・高配当狙い（オッズ100倍以上限定）")

      df_100plus = df_all[df_all["オッズ_num"] >= 100.0]

      if df_100plus.empty:
        st.info("※現在、このレースにはオッズ100倍以上の買い目が存在しません。")
      else:
        # ① 期待値最高
        top_ev_100 = df_100plus.sort_values(
            by="AI期待値", ascending=False
        ).iloc[0]

        # ② 理論値最高（AI予測確率が最も高い）
        top_prob_100 = df_100plus.sort_values(
            by="AI予測確率 (%)", ascending=False
        ).iloc[0]

        # ③ 完全ランダム
        random_100 = df_100plus.sample(n=1).iloc[0]

        cols_hole = st.columns(3)

        with cols_hole[0]:
          st.metric(
              label="🔥 高期待値 NO.1",
              value=top_ev_100["買い目 (3連単)"],
              delta=f"{top_ev_100['オッズ']} / 期待値:{top_ev_100['AI期待値']}",
          )

        with cols_hole[1]:
          st.metric(
              label="🎲 ランダム一発勝負",
              value=random_100["買い目 (3連単)"],
              delta=f"{random_100['オッズ']} / 期待値:{random_100['AI期待値']}",
          )

        with cols_hole[2]:
          st.metric(
              label="🧠 理論勝率 NO.1",
              value=top_prob_100["買い目 (3連単)"],
              delta=f"{top_prob_100['オッズ']} / 確率:{top_prob_100['AI予測確率 (%)']}%",
          )

        df_hole = (
            pd.DataFrame([top_ev_100, random_100, top_prob_100])
            .drop_duplicates(subset=["買い目 (3連単)"])
            .drop(columns=["オッズ_num"])
        )
        st.write("")
        st.dataframe(df_hole, hide_index=True, use_container_width=True)