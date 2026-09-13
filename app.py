from datetime import datetime
import pickle
import random
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from scraper import (
    check_race_time_status,
    create_features,
    get_active_places,
    get_odds_data,
    get_purchasable_races,
    get_race_data,
)
import streamlit as st

st.set_page_config(page_title="MYAI_BOATRACE v1.09", layout="wide")

jst = ZoneInfo("Asia/Tokyo")
now_jst = datetime.now(jst)
date_str = now_jst.strftime("%Y%m%d")


@st.cache_data(ttl=120, show_spinner=False)
def fetch_active_places_cached(target_date_str: str):
  try:
    places = get_active_places(target_date_str)
    return places if isinstance(places, dict) else {}
  except Exception as e:
    st.error(f"会場データ取得中にエラーが発生しました: {e}")
    return {}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_purchasable_races_cached(jcd: str, target_date_str: str):
  try:
    return get_purchasable_races(jcd, target_date_str)
  except Exception:
    return []


# --- ヘッダー ---
col_title, col_reload = st.columns([4, 1])
with col_title:
  st.markdown(
      '<h1 style="display: inline;">🚤 MYAI_BOATRACE </h1>'
      '<span style="font-size: 1.2rem; color: #888888; margin-left:'
      ' 8px;">v1.09</span>',
      unsafe_allow_html=True,
  )

with col_reload:
  st.write("")
  if st.button("🔄 最新情報に更新", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
formatted_datetime = f"{now_jst.strftime('%Y年%m月%d日')} ({WEEKDAYS_JP[now_jst.weekday()]}) {now_jst.strftime('%H:%M')}"
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
        trifecta[f"{i+1}-{j+1}-{k+1}"] = p_i_j_k * 100
  return trifecta


def generate_sample_predictions():
  combos = [
      f"{i}-{j}-{k}"
      for i in range(1, 7)
      for j in range(1, 7)
      for k in range(1, 7)
      if i != j and j != k and i != k
  ]
  predictions = []
  for idx, combo in enumerate(combos):
    odds = round(random.uniform(6.0, 350.0), 1)
    ai_prob = (
        round(random.uniform(2.0, 15.0), 1)
        if combo.startswith("1-")
        else round(random.uniform(0.1, 3.0), 2)
    )
    ev = round((ai_prob / 100) * odds, 2)
    predictions.append({
        "買い目": combo,
        "オッズ_num": odds,
        "オッズ": f"{odds:.1f}倍",
        "人気": f"{idx + 1}人気",
        "3連複オッズ": f"{round(odds * 0.25, 1)}倍",
        "AI予測確率_num": ai_prob,
        "AI期待値": ev,
        "AI期待値_str": f"{ev:.2f}",
    })
  return pd.DataFrame(predictions)


def highlight_high_ev(df):
  def apply_style(row):
    ev_val = float(row["AI期待値"])
    if ev_val >= 1.0:
      return ["color: #ff4b4b; font-weight: bold;" for _ in range(len(row))]
    return [""] * len(row)

  return df.style.apply(apply_style, axis=1)


# --- 開催会場の取得 ---
with st.spinner("現在開催中の会場を取得中..."):
  active_places = fetch_active_places_cached(date_str)

st.write("---")

if not active_places:
  st.warning(
      f"本日の日付（{date_str}）で開催中の会場データが取得できませんでした。\n\n"
      "・本日開催予定の全レースが終了している可能性があります。\n"
      "・「🔄 最新情報に更新」ボタンを押して再読み込みをお試しください。"
  )
else:
  col_place, col_race, col_btn, _ = st.columns([2, 2, 2, 4])

  with col_place:
    selected_place = st.selectbox("開催会場", list(active_places.keys()))
    jcd = active_places[selected_place]

  # 会場選択時にプログレスメッセージを表示
  with st.spinner(f"⏳ {selected_place}の開催中レースを取得中..."):
    purchasable_races = fetch_purchasable_races_cached(jcd, date_str)

  with col_race:
    if not purchasable_races:
      st.selectbox("対象レース", ["本日全R終了"], disabled=True)
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

  st.write("---")

  if submit_btn and selected_rno is not None:
    # 1. 締切時刻判定 (締切3分前チェック)
    time_status = check_race_time_status(jcd, selected_rno, date_str)

    if time_status["is_within_3min"]:
      st.error(
          "⚠️ 締切時間が3分前を過ぎているので、AI予測できません。"
      )
    else:
      with st.spinner(
          f"📊 {selected_place} {selected_rno}R"
          " のリアルタイムオッズ・直前情報を解析中..."
      ):
        df_raw = get_race_data(jcd, selected_rno, date_str)
        has_exhibit_info = df_raw.attrs.get("has_exhibit_time", False)

        # 2. 展示タイムなどの直前情報チェック
        if not has_exhibit_info:
          st.warning(
              "⚠️ 直前情報未取得（展示タイム等がまだ発表されていません）。"
          )
        else:
          odds_dict, odds_rank_dict, trio_odds_dict = get_odds_data(
              jcd, selected_rno, date_str
          )

          if not odds_dict:
            st.error("オッズデータの取得に失敗しました。")
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
              rank = odds_rank_dict.get(combo, "-")
              trio_key = "-".join(sorted(combo.split("-")))
              trio_odds = trio_odds_dict.get(trio_key, 0.0)

              ev = (ai_prob / 100) * odds

              predictions.append({
                  "買い目": combo,
                  "オッズ_num": odds,
                  "オッズ": f"{odds:.1f}倍",
                  "人気": f"{rank}人気" if str(rank).isdigit() else "-",
                  "3連複オッズ": f"{trio_odds:.1f}倍" if trio_odds > 0 else "-",
                  "AI予測確率_num": ai_prob,
                  "AI期待値": round(ev, 2),
                  "AI期待値_str": f"{ev:.2f}",
              })

            df_all = pd.DataFrame(predictions)

            st.toast(
                "✅ 最新オッズとAI予想結果を出力しました！", icon="🎉"
            )

            DISPLAY_COLS = [
                "買い目",
                "オッズ",
                "人気",
                "3連複オッズ",
                "AI期待値",
            ]

            st.subheader(
                f"🏆 {selected_place} {selected_rno}R AI厳選買い目(上位5点)"
            )
            df_top5 = (
                df_all.sort_values(by="AI期待値", ascending=False).head(5).copy()
            )
            df_top5["AI期待値"] = df_top5["AI期待値_str"]

            st.dataframe(
                highlight_high_ev(df_top5[DISPLAY_COLS]),
                hide_index=True,
                use_container_width=True,
            )

            st.write("---")

            st.subheader("💥 万舟・高配当狙い（オッズ100倍以上限定）")
            df_100plus = df_all[df_all["オッズ_num"] >= 100.0]

            if df_100plus.empty:
              st.info(
                  "※現在、このレースにはオッズ100倍以上の買い目が存在しません。"
              )
            else:
              top_ev_100 = df_100plus.sort_values(
                  by="AI期待値", ascending=False
              ).iloc[0]
              top_prob_100 = df_100plus.sort_values(
                  by="AI予測確率_num", ascending=False
              ).iloc[0]
              random_100 = df_100plus.sample(n=1).iloc[0]

              cols_hole = st.columns(3)
              with cols_hole[0]:
                st.metric(
                    label="🔥 高期待値 NO.1",
                    value=top_ev_100["買い目"],
                    delta=(
                        f"{top_ev_100['オッズ']} /"
                        f" 期待値:{top_ev_100['AI期待値_str']}"
                    ),
                )
              with cols_hole[1]:
                st.metric(
                    label="🎯 注目買い目",
                    value=top_prob_100["買い目"],
                    delta=(
                        f"{top_prob_100['オッズ']} /"
                        f" 期待値:{top_prob_100['AI期待値_str']}"
                    ),
                )
              with cols_hole[2]:
                st.metric(
                    label="🎲 ランダム一発勝負",
                    value=random_100["買い目"],
                    delta=(
                        f"{random_100['オッズ']} /"
                        f" 期待値:{random_100['AI期待値_str']}"
                    ),
                )

              df_hole = (
                  pd.DataFrame([top_ev_100, top_prob_100, random_100])
                  .drop_duplicates(subset=["買い目"])
                  .copy()
              )
              df_hole["AI期待値"] = df_hole["AI期待値_str"]

              st.write("")
              st.dataframe(
                  highlight_high_ev(df_hole[DISPLAY_COLS]),
                  hide_index=True,
                  use_container_width=True,
              )

            st.write("---")
            st.markdown(
                "💡 **AI期待値**："
                " (AI予測確率 ÷ 100) ×"
                " オッズで算出される購入コストに対する回収見込み（1.00以上が買い価値あり）です。"
            )

# --- ページ最下部：サンプルデータ確認エリア ---
st.write("---")
st.write("")
use_sample = st.checkbox(
    "🧪 サンプルデータで表示結果を確認する（夜間・非開催時デモ用）"
)

if use_sample:
  st.info("💡 サンプルデータ（住之江 12R想定）のAI予測デモを表示しています。")
  df_sample = generate_sample_predictions()
  DISPLAY_COLS = ["買い目", "オッズ", "人気", "3連複オッズ", "AI期待値"]

  st.subheader("🏆 [サンプル] AI厳選買い目(上位5点)")
  df_sample_top5 = (
      df_sample.sort_values(by="AI期待値", ascending=False).head(5).copy()
  )
  df_sample_top5["AI期待値"] = df_sample_top5["AI期待値_str"]
  st.dataframe(
      highlight_high_ev(df_sample_top5[DISPLAY_COLS]),
      hide_index=True,
      use_container_width=True,
  )