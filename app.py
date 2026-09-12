import json
import os
import pandas as pd
import streamlit as st

# ブラウザタブのタイトル設定
st.set_page_config(page_title="MYAI_BOATRACE", layout="wide")


# キャッシュクリアと通知フラグの設定
def refresh_data():
  st.cache_data.clear()
  st.session_state["show_toast"] = True


# ヘッダーエリア（タイトルと更新ボタン）
col_title, col_btn = st.columns([4, 1])
with col_title:
  st.title("🚤 MYAI_BOATRACE")
with col_btn:
  st.write("")  # レイアウト調整用
  if st.button("🔄 データを最新に更新", on_click=refresh_data):
    st.rerun()

# 更新完了時のポップアップ通知（画面右下に約3秒表示されて自動消滅）
if st.session_state.get("show_toast", False):
  st.toast("✅ データを最新に更新しました！", icon="🎉")
  st.session_state["show_toast"] = False  # 次回描画時に再表示されないようリセット


@st.cache_data(ttl=600)
def load_predictions():
  if not os.path.exists("latest_predictions.json"):
    return None
  with open("latest_predictions.json", "r", encoding="utf-8") as f:
    return json.load(f)


pred_data = load_predictions()

if pred_data is None:
  st.warning(
      "現在予測データがありません。GitHub Actionsの実行をお待ちください。"
  )
else:
  st.caption(f"最終更新日時: {pred_data.get('updated_at')}")

  places_data = pred_data.get("data", {})
  place_options = {
      v["place_name"]: k
      for k, v in places_data.items()
      if len(v.get("races", {})) > 0
  }

  if not place_options:
    st.info("本日の開催レースデータはまだ更新されていません。")
  else:
    st.sidebar.header("📌 レース選択")

    # サイドバー側の更新ボタン
    if st.sidebar.button(
        "🔄 予想データを再取得",
        key="sidebar_refresh",
        on_click=refresh_data,
    ):
      st.rerun()

    selected_place_name = st.sidebar.selectbox(
        "開催場", list(place_options.keys())
    )
    selected_jcd = place_options[selected_place_name]

    races_available = places_data[selected_jcd]["races"]
    selected_rno = st.sidebar.slider("レース番号", 1, 12, 1)

    rno_str = str(selected_rno)

    if rno_str in races_available:
      race_info = races_available[rno_str]
      rank_preds = race_info["ranks"]
      trifecta_preds = race_info["trifecta"]

      # 表データの作成
      df_result = pd.DataFrame(rank_preds)
      df_result["boat"] = df_result["boat"].apply(lambda x: f"{x}号艇")
      df_result.columns = [
          "艇番",
          "1着確率 (%)",
          "2着確率 (%)",
          "3着確率 (%)",
      ]

      st.subheader(f"🎯 {selected_place_name} {selected_rno}R 着順予測")
      st.dataframe(df_result, hide_index=True, use_container_width=True)

      # 3連単おすすめ買い目の表示
      st.subheader("💡 AI推奨 3連単買い目（上位5点）")
      cols = st.columns(5)
      for idx, (combo, prob) in enumerate(trifecta_preds):
        with cols[idx]:
          st.metric(label=f"第{idx+1}予想", value=combo, delta=f"{prob}%")

    else:
      st.warning(
          f"{selected_place_name} {selected_rno}R の予測データはありません。"
      )