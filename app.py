from datetime import datetime, timedelta
import pickle
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from scraper import (
    ALL_PLACES,
    create_features,
    get_active_places,
    get_odds_data,
    get_purchasable_races,
    get_race_data,
    get_race_results,
)
import streamlit as st

st.set_page_config(page_title="MYAI_BOATRACE", layout="wide")


# --- キャッシュ定義 ---
@st.cache_data(ttl=600, show_spinner=False)
def fetch_active_places_cached(target_date_str: str):
  return get_active_places(target_date_str)


# --- ヘッダーエリア ---
col_title, col_reload = st.columns([4, 1])

with col_title:
  st.title("🚤 MYAI_BOATRACE")

with col_reload:
  st.write("")
  if st.button("🔄 キャッシュクリア & 再読み込み", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

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


# --- サイドバー：過去日付検証機能 ---
st.sidebar.header("📜 過去レース検証（バックテスト）")
enable_backtest = st.sidebar.checkbox("過去データ検証モードを有効化", value=False)

if enable_backtest:
  yesterday = now_jst.date() - timedelta(days=1)
  selected_backtest_date = st.sidebar.date_input(
      "検証日付（過去日）",
      value=yesterday,
      max_value=yesterday,
  )
  backtest_date_str = selected_backtest_date.strftime("%Y%m%d")

  with st.spinner("指定日付の開催会場を取得中..."):
    bt_active_places = fetch_active_places_cached(backtest_date_str)

  # 会場データが取得できない場合、全会場を選択肢として表示するフォールバック
  if not bt_active_places:
    st.sidebar.warning(
        "⚠️ 自動会場取得がタイムアウトしたため、全会場一覧を表示します。"
    )
    bt_active_places = ALL_PLACES

  bt_place_options = list(bt_active_places.keys())
  selected_bt_place = st.sidebar.selectbox(
      "検証会場（指定日の開催場）", bt_place_options
  )
  bt_jcd = bt_active_places[selected_bt_place]

  top_n_choice = st.sidebar.slider("AI期待値 上位何点を購入するか", 1, 10, 5)

  if st.sidebar.button("🚀 過去全12レースの検証実行", type="primary"):
    st.subheader(
        f"📊 {selected_backtest_date.strftime('%Y年%m月%d日')} {selected_bt_place} 全レース検証結果"
    )

    results = []
    hits_count = 0
    total_races = 12
    progress_bar = st.progress(0)

    for rno in range(1, 13):
      df_raw = get_race_data(bt_jcd, rno, backtest_date_str)
      odds_dict, odds_rank_dict, trio_odds_dict = get_odds_data(
          bt_jcd, rno, backtest_date_str
      )
      actual_result = get_race_results(bt_jcd, rno, backtest_date_str)

      if df_raw is not None and not df_raw.empty:
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
          predictions.append({"買い目": combo, "オッズ": odds, "AI期待値": ev})

        df_pred = pd.DataFrame(predictions)
        top_preds = (
            df_pred.sort_values(by="AI期待値", ascending=False)
            .head(top_n_choice)["買い目"]
            .tolist()
        )

        is_hit = actual_result in top_preds if actual_result else False
        if is_hit:
          hits_count += 1

        results.append({
            "レース": f"{rno}R",
            "AI予測上位買い目": ", ".join(top_preds),
            "実際の結果": actual_result if actual_result else "データ無",
            "判定": "🎯 的中" if is_hit else "❌ 不的中",
        })
      else:
        results.append({
            "レース": f"{rno}R",
            "AI予測上位買い目": "データなし",
            "実際の結果": "-",
            "判定": "中止/データ無",
        })

      progress_bar.progress(rno / 12)

    hit_rate = (hits_count / total_races) * 100

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("対象レース数", f"{total_races} レース")
    col_m2.metric("的中数", f"{hits_count} レース")
    col_m3.metric("的中率", f"{hit_rate:.1f} %")

    st.dataframe(
        pd.DataFrame(results), hide_index=True, use_container_width=True
    )
    st.write("---")

# ---------------------------------------------------------
# リアルタイムモード（過去データ検証モードがOFFの時に必ず常表示）
# ---------------------------------------------------------
else:
  with st.spinner("本日の開催会場データを読み込み中..."):
    active_places = fetch_active_places_cached(date_str)

  # 万が一本日開催会場が通信エラーで取得できない場合も全会場一覧を表示
  if not active_places:
    st.info(
        "💡 本日の開催会場データを取得中のため、全会場リストより選択可能です。"
    )
    active_places = ALL_PLACES

  col_place, col_race, col_btn, _ = st.columns([2, 2, 2, 4])

  with col_place:
    selected_place = st.selectbox("開催会場", list(active_places.keys()))
    jcd = active_places[selected_place]

  purchasable_races = get_purchasable_races(jcd, date_str)

  with col_race:
    if not purchasable_races:
      race_options = [f"{r}R" for r in range(1, 13)]
    else:
      race_options = [f"{r}R" for r in purchasable_races]

    selected_race_str = st.selectbox("対象レース", race_options)
    selected_rno = int(selected_race_str.replace("R", ""))

  with col_btn:
    st.write("")
    st.write("")
    submit_btn = st.button(
        "🎯 決定（予想実行）", type="primary", use_container_width=True
    )

  st.write("---")

  if submit_btn and selected_rno:
    with st.spinner(f"{selected_place} {selected_rno}R のデータを取得中..."):
      df_raw = get_race_data(jcd, selected_rno, date_str)
      odds_dict, odds_rank_dict, trio_odds_dict = get_odds_data(
          jcd, selected_rno, date_str
      )

      if df_raw is not None and not df_raw.empty:
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
          rank = odds_rank_dict.get(combo, "-")
          ev = (ai_prob / 100) * odds
          predictions.append({
              "買い目": combo,
              "オッズ": f"{odds:.1f}倍",
              "人気": f"{rank}人気" if str(rank).isdigit() else "-",
              "AI予測確率": f"{round(ai_prob, 1)}%",
              "AI期待値": round(ev, 2),
          })

        st.subheader(f"🏆 {selected_place} {selected_rno}R AI厳選買い目(上位5点)")
        st.dataframe(
            pd.DataFrame(predictions)
            .sort_values(by="AI期待値", ascending=False)
            .head(5),
            hide_index=True,
            use_container_width=True,
        )