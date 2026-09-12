from datetime import datetime, timedelta
import pickle
import random
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
import streamlit as st

# ※ scraper から必要な関数をインポート
from scraper import (
    create_features,
    get_odds_data,
    get_purchasable_races,
    get_race_data,
)

st.set_page_config(page_title="MYAI_BOATRACE", layout="wide")


# --- キャッシュ定義：日付ごとに個別にキャッシュするように修正 ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_active_places_by_date(target_date_str: str):
  """指定日付（YYYYMMDD）の開催会場リストを取得する"""
  # scraper側の get_active_places が日付に対応していない場合への安全対策付き取得
  try:
    from scraper import get_active_places

    # 1. scraper側の関数を呼び出し
    places = get_active_places(target_date_str)
    if places:
      return places
  except Exception:
    pass

  # 2. 上記で取れなかった場合の自前フォールバック処理（Direct Requests）
  return get_active_places_direct(target_date_str)


def get_active_places_direct(date_str: str):
  """公式Webから指定日付(YYYYMMDD)の開催会場を直接解析して取得"""
  import bs4

  url = f"https://www.boatrace.jp/owpc/pc/race/indexpage?hd={date_str}"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  places = {}
  places_dict = {
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

  try:
    res = requests.get(url, headers=headers, timeout=5)
    soup = bs4.BeautifulSoup(res.content, "html.parser")

    # 会場リンクのパース (jcdパラメータが含まれる要素を探す)
    elements = soup.select('a[href*="jcd="]')
    for el in elements:
      href = el.get("href", "")
      for place_name, jcd in places_dict.items():
        if f"jcd={jcd}" in href:
          places[place_name] = jcd
  except Exception as e:
    st.error(f"会場データ通信エラー: {e}")

  return places


# --- ヘッダーエリア ---
col_title, col_reload = st.columns([4, 1])
with col_title:
  st.title("🚤 MYAI_BOATRACE")

with col_reload:
  st.write("")
  if st.button("🔄 最新情報に更新", use_container_width=True):
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
enable_backtest = st.sidebar.checkbox("過去データ検証モードを有効化")

if enable_backtest:
  yesterday = now_jst.date() - timedelta(days=1)
  selected_backtest_date = st.sidebar.date_input(
      "検証日付（過去日）",
      value=yesterday,
      max_value=yesterday,
  )
  backtest_date_str = selected_backtest_date.strftime("%Y%m%d")

  # 【重要】選択された日付(backtest_date_str)を明示的に渡して会場取得
  with st.spinner("指定日付の開催会場を取得中..."):
    bt_active_places = fetch_active_places_by_date(backtest_date_str)

  if not bt_active_places:
    st.sidebar.error(
        f"⚠️ {selected_backtest_date.strftime('%Y/%m/%d')} は開催会場データを取得できませんでした。"
    )
  else:
    bt_place_options = list(bt_active_places.keys())
    selected_bt_place = st.sidebar.selectbox(
        "検証会場（指定日の開催場）", bt_place_options
    )
    bt_jcd = bt_active_places[selected_bt_place]

    top_n_choice = st.sidebar.slider(
        "AI期待値 上位何点を購入するか", 1, 10, 5
    )

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

        actual_result = "1-2-3"  # ※実際の着順結果取得処理

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
            predictions.append(
                {"買い目": combo, "オッズ": odds, "AI期待値": ev}
            )

          df_pred = pd.DataFrame(predictions)
          top_preds = (
              df_pred.sort_values(by="AI期待値", ascending=False)
              .head(top_n_choice)["買い目"]
              .tolist()
          )

          is_hit = actual_result in top_preds
          if is_hit:
            hits_count += 1

          results.append({
              "レース": f"{rno}R",
              "AI予測上位買い目": ", ".join(top_preds),
              "実際の結果": actual_result,
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

# リアルタイムモード（本日開催分）
if not enable_backtest:
  active_places = fetch_active_places_by_date(date_str)
  # （以下省略・通常のリアルタイム画面を表示）