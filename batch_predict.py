from datetime import datetime
import json
import numpy as np
import pandas as pd
import pickle
from scraper import create_features, get_race_data

# 競艇場リスト
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
    "national_win_rate",
    "local_win_rate",
    "motor_2in_rate",
    "exhibit_time",
    "is_boat_1",
    "has_flying",
    "boat1_and_flying",
    "ex_time_rel",
    "st_rel",
]


def main():
  # モデル読み込み
  with open("boat_model.pkl", "rb") as f:
    model = pickle.load(f)

  today_str = datetime.now().strftime("%Y%m%d")
  all_results = {}

  # 主要な会場・レースを一気に予測（例: 01〜24場の1〜12R）
  for jcd, name in JCD_MAP.items():
    all_results[jcd] = {"place_name": name, "races": {}}

    for rno in range(1, 13):
      df_raw = get_race_data(jcd, rno, today_str)
      if df_raw is None or df_raw.empty:
        continue

      # 特徴量生成 & 予測
      df_features = create_features(df_raw)
      probs = model.predict_proba(df_features[FEATURE_COLS])[:, 1]
      norm_probs = (probs / np.sum(probs)) * 100

      race_pred = []
      for i, prob in enumerate(norm_probs, start=1):
        race_pred.append({"boat": i, "prob": round(float(prob), 1)})

      # 勝率が高い順にソート
      race_pred.sort(key=lambda x: x["prob"], reverse=True)
      all_results[jcd]["races"][str(rno)] = race_pred

  # 結果をJSON保存
  output_data = {"updated_at": today_str, "data": all_results}

  with open("latest_predictions.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

  print("全レースの予測更新が完了しました！")


if __name__ == "__main__":
  main()