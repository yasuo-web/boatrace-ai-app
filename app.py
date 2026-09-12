from datetime import datetime
import json
import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="AI競艇予想 Webアプリ (全自動更新版)", layout="wide"
)
st.title("🚤 AI競艇予想 Webアプリ（自動更新版）")


# JSONデータの読み込み
@st.cache_data(ttl=600)  # 10分キャッシュ
def load_predictions():
  if not os.path.exists("latest_predictions.json"):
    return None
  with open("latest_predictions.json", "r", encoding="utf-8") as f:
    return json.load(f)


pred_data = load_predictions()

if pred_data is None:
  st.warning(
      "現在予測データがありません。GitHub Actionsの初回実行をお待ちください。"
  )
else:
  st.caption(f"最終更新日: {pred_data.get('updated_at')}")

  places_data = pred_data.get("data", {})
  place_options = {
      v["place_name"]: k
      for k, v in places_data.items()
      if len(v["races"]) > 0
  }

  if not place_options:
    st.info("本日の開催レースデータはまだ更新されていません。")
  else:
    st.sidebar.header("📌 レース選択")
    selected_place_name = st.sidebar.selectbox(
        "開催場", list(place_options.keys())
    )
    selected_jcd = place_options[selected_place_name]

    races_available = places_data[selected_jcd]["races"]
    selected_rno = st.sidebar.slider("レース番号", 1, 12, 1)

    rno_str = str(selected_rno)

    if rno_str in races_available:
      race_preds = races_available[rno_str]

      df_result = pd.DataFrame(race_preds)
      df_result.columns = ["艇番", "予想勝利確率 (%)"]
      df_result["艇番"] = df_result["艇番"].apply(lambda x: f"{x}号艇")

      st.subheader(f"🎯 {selected_place_name} {selected_rno}R 予想結果")
      st.dataframe(df_result, hide_index=True, use_container_width=True)

      # 本命・対抗の強調表示
      top1 = df_result.iloc[0]["艇番"]
      top2 = df_result.iloc[1]["艇番"]
      st.success(f"**本命 (◎):** {top1} | **対抗 (○):** {top2}")
    else:
      st.warning(
          f"{selected_place_name} {selected_rno}R の予測データはありません。"
      )