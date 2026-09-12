from datetime import datetime
import pickle
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

# ヘッダーエリア
st.title("🚤 MYAI_BOATRACE")

# 本日日付の設定・表示
today_dt = datetime.now()
date_str = today_dt.strftime("%Y%m%d")
st.caption(f"📅 対象日: {today_dt.strftime('%Y年%m月%d日 (%a)')}")

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


# --- 本日開催会場の動的取得 ---
with st.spinner("本日開催中の会場を取得中..."):
  active_places = get_active_places(date_str)

st.write("---")

if not active_places:
  st.warning(
      "現在開催中の会場がないか、本日のレース日程が終了している可能性があります。"
  )
else:
  # 4列レイアウト（開催会場 / レース番号 / 決定ボタン）
  col_place, col_race, col_btn, _ = st.columns([2, 2, 2, 4])

  with col_place:
    selected_place = st.selectbox("開催会場", list(active_places.keys()))
    jcd = active_places[selected_place]

  # 選択された会場で「現在購入可能（締切前）」なレース番号を取得
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

  st.write("---")

  # 決定ボタン押下時の処理
  if submit_btn and selected_rno is not None:
    with st.spinner(
        f"{selected_place} {selected_rno}R の最新データ・オッズを取得中..."
    ):
      # 1. レース・展示データ取得
      df_raw = get_race_data(jcd, selected_rno, date_str)
      odds_dict = get_odds_data(jcd, selected_rno, date_str)

      if df_raw is None or df_raw.empty:
        st.error(
            "レースデータの取得に失敗しました。直前データ更新前などの可能性があります。"
        )
      else:
        # 2. AI確率計算
        df_features = create_features(df_raw)
        probs = model.predict_proba(df_features[FEATURE_COLS])[:, 1]
        trifecta_probs = calculate_trifecta_probs(probs)

        # 3. オッズ結合とAI期待値算出
        predictions = []
        for combo, ai_prob in trifecta_probs.items():
          odds = odds_dict.get(combo, 10.0)
          ev = (ai_prob / 100) * odds

          predictions.append({
              "買い目 (3连単)": combo,
              "AI予測確率 (%)": round(ai_prob, 1),
              "オッズ": f"{odds:.1f}倍",
              "AI期待値": round(ev, 2),
          })

        # 4. 期待値上位5点の抽出
        df_top5 = (
            pd.DataFrame(predictions)
            .sort_values(by="AI期待値", ascending=False)
            .head(5)
        )

        # 5. 結果出力
        st.toast("✅ 予想結果を出力しました！", icon="🎉")
        st.subheader(
            f"🏆 {selected_place} {selected_rno}R AI厳選買い目（上位5点）"
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
        st.dataframe(df_top5, hide_index=True, use_container_width=True)