from datetime import datetime
import json
import numpy as np
import pandas as pd
import pickle
from scraper import create_features, get_race_data

JCD_MAP = {
    "01": "桐生",
    "02": "戸田",
    "03": "江戸川",
    "04": "平和島",
    "05": "多摩川",
    "06": "浜名湖",
    "07": "蒲郡",
    "08": "常滑",
    "09": "津",
    "10": "三国",
    "11": "びわこ",
    "12": "住之江",
    "13": "尼崎",
    "14": "鳴門",
    "15": "丸亀",
    "16": "児島",
    "17": "宮島",
    "18": "徳山",
    "19": "下関",
    "20": "若松",
    "21": "芦屋",
    "22": "福岡",
    "23": "唐津",
    "24": "大村",
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


def calculate_rank_probabilities(p):
  """各艇の強さスコア(1着確率p)から1着・2着・3着確率および3連単確率を計算"""
  p = np.array(p)
  p = p / np.sum(p)  # 正規化
  n = len(p)

  p1 = p.copy()  # 1着確率
  p2 = np.zeros(n)  # 2着確率
  p3 = np.zeros(n)  # 3着確率

  trifecta = {}  # 3連単の確率

  # 全パターンの3連単確率を計算 (Plackett-Luce Model)
  for i in range(n):
    for j in range(n):
      if i == j:
        continue
      p_i_j = p[i] * (p[j] / (1 - p[i]))
      p2[j] += p_i_j

      for k in range(n):
        if k == i or k == j:
          continue
        p_i_j_k = p_i_j * (p[k] / (1 - p[i] - p[j]))
        p3[k] += p_i_j_k

        # 買い目文字列 (例: "1-2-3")
        combo = f"{i+1}-{j+1}-{k+1}"
        trifecta[combo] = round(float(p_i_j_k * 100), 2)

  # 3連単確率の高い順にソートして上位5点抽出
  top_trifecta = sorted(
      trifecta.items(), key=lambda item: item[1], reverse=True
  )[:5]

  results = []
  for i in range(n):
    results.append({
        "boat": i + 1,
        "prob_1st": round(float(p1[i] * 100), 1),
        "prob_2nd": round(float(p2[i] * 100), 1),
        "prob_3rd": round(float(p3[i] * 100), 1),
    })

  # 1着確率が高い順にソート
  results.sort(key=lambda x: x["prob_1st"], reverse=True)

  return results, top_trifecta


def main():
  with open("boat_model.pkl", "rb") as f:
    model = pickle.load(f)

  today_str = datetime.now().strftime("%Y%m%d")
  all_results = {}

  for jcd, name in JCD_MAP.items():
    all_results[jcd] = {"place_name": name, "races": {}}

    for rno in range(1, 13):
      df_raw = get_race_data(jcd, rno, today_str)
      if df_raw is None or df_raw.empty:
        continue

      df_features = create_features(df_raw)
      probs = model.predict_proba(df_features[FEATURE_COLS])[:, 1]

      # 1,2,3着確率および3連単買い目を算出
      rank_probs, top_trifecta = calculate_rank_probabilities(probs)

      all_results[jcd]["races"][str(rno)] = {
          "ranks": rank_probs,
          "trifecta": top_trifecta,
      }

  output_data = {"updated_at": today_str, "data": all_results}

  with open("latest_predictions.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

  print("順位予測・買い目データの計算が完了しました！")


if __name__ == "__main__":
  main()