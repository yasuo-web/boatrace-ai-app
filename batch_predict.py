import os
import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime

# ==========================================
# 定数・設定
# ==========================================
MODEL_PATH = "model.gbdt"  # 学習済みモデルのパス
LATEST_OUTPUT_PATH = "latest_predictions.json"
HISTORY_DIR = "history"

STADIUMS = [
    "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", 
    "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", 
    "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", 
    "下関", "若松", "芦屋", "福岡", "唐津", "大村"
]

# ==========================================
# 処理本体
# ==========================================
def load_model():
    """モデルの読み込み"""
    if os.path.exists(MODEL_PATH):
        return lgb.Booster(model_file=MODEL_PATH)
    return None

def fetch_today_race_data():
    """
    当日開催データの取得スクリプト（ダミー/スクレイピング処理）
    ※ 実際の実装に合わせて取得ロジックを配置してください。
    """
    # サンプル用データ構造
    race_data_list = []
    for stadium in ["住之江", "蒲郡"]:  # 開催会場例
        for r in range(1, 13):
            race_key = f"{stadium}_{r}R"
            race_data_list.append({
                "race_key": race_key,
                "stadium": stadium,
                "race_num": f"{r}R",
                # モデルに入力する特徴量データなど
                "features": {}
            })
    return race_data_list

def predict_race(model, race_info):
    """
    1レース分の予測処理
    """
    # 実際のモデル予測結果・買い目生成ロジック
    # ここでは例としてサンプルデータを返却します
    predictions = [
        {"combination": "1-2-3", "probability": 0.25, "odds": 8.5, "expected_value": 2.125},
        {"combination": "1-3-2", "probability": 0.18, "odds": 12.0, "expected_value": 2.16},
        {"combination": "1-2-4", "probability": 0.12, "odds": 15.3, "expected_value": 1.836},
        {"combination": "2-1-3", "probability": 0.08, "odds": 45.0, "expected_value": 3.60},
        {"combination": "3-1-2", "probability": 0.02, "odds": 120.0, "expected_value": 2.40}, # 万舟例
    ]
    return predictions

def run_batch_predict():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    model = load_model()
    races = fetch_today_race_data()
    
    all_top_predictions = []
    all_high_odds_predictions = []
    history_race_dict = {}

    for race in races:
        race_key = race["race_key"]
        preds = predict_race(model, race)
        
        # 1. 最新表示用（上位・万舟）のフィルタリング処理
        for p in preds:
            p_item = {
                "stadium": race["stadium"],
                "race": race["race_num"],
                "combination": p["combination"],
                "odds": p["odds"],
                "probability": p["probability"],
                "expected_value": p["expected_value"]
            }
            all_top_predictions.append(p_item)
            
            # 100倍以上を万舟フラグとして抽出
            if p["odds"] >= 100.0:
                all_high_odds_predictions.append(p_item)

        # 2. 過去検証用ログデータの構成
        history_race_dict[race_key] = {
            "stadium": race["stadium"],
            "race": race["race_num"],
            "predictions": preds,
            "actual_results": [],  # 確定着順（結果取得時に更新）
            "payout_summary": "未確定"
        }

    # 上位順にソート（期待値または確率順）
    all_top_predictions = sorted(all_top_predictions, key=lambda x: x["expected_value"], reverse=True)[:5]
    all_high_odds_predictions = sorted(all_high_odds_predictions, key=lambda x: x["odds"], reverse=True)

    # --------------------------------------------------
    # A. 最新予測データ（latest_predictions.json）の保存
    # --------------------------------------------------
    latest_payload = {
        "updated_at": now_str,
        "top_predictions": all_top_predictions,
        "high_odds_predictions": all_high_odds_predictions
    }
    
    with open(LATEST_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(latest_payload, f, ensure_ascii=False, indent=2)
    print(f"[{now_str}] {LATEST_OUTPUT_PATH} を更新しました。")

    # --------------------------------------------------
    # B. 過去検証用データ（history/YYYY-MM-DD.json）の保存
    # --------------------------------------------------
    os.makedirs(HISTORY_DIR, exist_ok=True)
    history_file_path = os.path.join(HISTORY_DIR, f"{today_str}.json")
    
    existing_history = {}
    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, "r", encoding="utf-8") as f:
                existing_history = json.load(f)
        except json.JSONDecodeError:
            existing_history = {}

    # 既存ログに対して本日の予測データを統合（更新）
    existing_history.update(history_race_dict)

    with open(history_file_path, "w", encoding="utf-8") as f:
        json.dump(existing_history, f, ensure_ascii=False, indent=2)
    print(f"[{now_str}] 検証用ログ {history_file_path} を保存しました。")

if __name__ == "__main__":
    run_batch_predict()