import pickle
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI競艇予想アプリ", layout="wide")

st.title("🚤 AI競艇予想 Webアプリ")
st.write("各艇のデータを入力すると、AIが勝率を予測します。")


# モデルの読み込み
@st.cache_resource
def load_model():
  with open("boat_model.pkl", "rb") as f:
    return pickle.load(f)


model = load_model()

# 入力フォーム
st.subheader("📋 出走表データ入力")

input_data = []
for i in range(1, 7):
  st.write(f"**{i}号艇**")
  col1, col2, col3 = st.columns(3)
  with col1:
    nat_win = st.number_input(
        f"全国勝率 ({i}号艇)", 1.0, 10.0, 5.0 + (6 - i) * 0.2, key=f"nat_{i}"
    )
  with col2:
    motor = st.number_input(
        f"モーター2連率% ({i}号艇)",
        0.0,
        100.0,
        30.0,
        key=f"mot_{i}",
    )
  with col3:
    ex_time = st.number_input(
        f"展示タイム ({i}号艇)", 6.0, 8.0, 6.70, key=f"ex_{i}"
    )

  input_data.append({
      "boat_number": i,
      "national_win_rate": nat_win,
      "local_win_rate": nat_win,  # 簡易的に同値
      "motor_2in_rate": motor,
      "exhibit_time": ex_time,
  })

df_input = pd.DataFrame(input_data)

# 予測ボタン
if st.button("AIで勝率を予想する", type="primary"):
  # 確率推論
  probs = model.predict_proba(
      df_input[
          [
              "boat_number",
              "national_win_rate",
              "local_win_rate",
              "motor_2in_rate",
              "exhibit_time",
          ]
      ]
  )[:, 1]

  # 確率を100%に正規化
  total_prob = np.sum(probs)
  norm_probs = (probs / total_prob) * 100

  df_result = pd.DataFrame({
      "艇番": [f"{i}号艇" for i in range(1, 7)],
      "予想勝利確率 (%)": np.round(norm_probs, 1),
  }).sort_values(by="予想勝利確率 (%)", ascending=False)

  st.subheader("🎯 予想結果")
  st.dataframe(df_result, hide_index=True, use_container_width=True)

  # 本命・対抗の表示
  top1 = df_result.iloc[0]["艇番"]
  top2 = df_result.iloc[1]["艇番"]
  st.success(f"**本命 (◎):** {top1} | **対抗 (○):** {top2}")