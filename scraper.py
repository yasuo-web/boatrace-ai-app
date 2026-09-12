import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import requests


def get_race_data(jcd: str, rno: int, date_str: str) -> pd.DataFrame:
  url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd:02s}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  res = requests.get(url, headers=headers)
  res.encoding = res.apparent_encoding

  if res.status_code != 200:
    return None

  soup = BeautifulSoup(res.text, "html.parser")
  tables = soup.find_all("table", class_="is-w780")
  if not tables:
    return None

  rows = tables[0].find_all("tbody")
  race_data = []

  for i, row in enumerate(rows, start=1):
    cols = row.find_all("td")
    if len(cols) < 4:
      continue

    try:
      # 1. 選手ランクの取得 (A1, A2, B1, B2)
      rank_text = cols[2].get_text(strip=True)
      if "A1" in rank_text:
        rank_val = 4
      elif "A2" in rank_text:
        rank_val = 3
      elif "B1" in rank_text:
        rank_val = 2
      else:
        rank_val = 1

      # 2. 全国勝率
      rates_text = cols[4].get_text(strip=True)
      nat_win = float(rates_text.split("%")[0]) if "%" in rates_text else 5.0

      # 3. F数・平均ST
      st_text = cols[3].get_text(strip=True)
      f_count = 1 if "F1" in st_text else (2 if "F2" in st_text else 0)
      st_match = re.search(r"0\.\d+", st_text)
      avg_st = float(st_match.group(0)) if st_match else 0.17

      # 4. 進入コース（直前展示データや出走表から。デフォルトは艇番通り）
      entry_course = i  # 前付け等の展示侵入があればそのコース番号

    except Exception:
      rank_val = 2
      nat_win = 5.0
      f_count = 0
      avg_st = 0.17
      entry_course = i

    race_data.append({
        "boat_number": i,
        "rank_score": rank_val,
        "national_win_rate": nat_win,
        "local_win_rate": nat_win,
        "motor_2in_rate": 30.0,
        "exhibit_time": 6.70,
        "f_count": f_count,
        "avg_st": avg_st,
        "entry_course": entry_course,
    })

  time.sleep(1)
  return pd.DataFrame(race_data)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
  """展開・進入・ランクを考慮した特徴量生成エンジン"""
  df = df.copy()

  # --- 基本特徴量 ---
  df["is_boat_1"] = (df["boat_number"] == 1).astype(int)
  df["has_flying"] = (df["f_count"] > 0).astype(int)

  # --- 進入コース・枠なり崩れ特徴量 ---
  # 実際に入ったコースが1コースかどうか（6号艇がイン進入した場合は1になる）
  df["is_course_1"] = (df["entry_course"] == 1).astype(int)
  # 枠なり崩れ（前付け等で艇番と違うコースに入ったフラグ）
  df["course_changed"] = (df["boat_number"] != df["entry_course"]).astype(int)

  # --- 相対値特徴量 ---
  df["ex_time_rel"] = df["exhibit_time"] - df["exhibit_time"].mean()
  df["st_rel"] = df["avg_st"] - df["avg_st"].mean()

  # --- 展開シナリオ特徴量 (まくり・連対パターン) ---
  # 3・4カドのまくり脅威度: (平均STが早い + ランクが高い)
  kadomakuri_score = df.apply(
      lambda r: (0.25 - r["avg_st"]) * r["rank_score"]
      if r["entry_course"] in [3, 4]
      else 0,
      axis=1,
  ).max()
  df["kadomakuri_threat"] = kadomakuri_score

  # 4カドまくり時の外枠追随フラグ（4号艇が強力な時、5号艇の展開恵まれ度を上げる）
  is_boat4_strong = (
      (df["entry_course"] == 4) & (df["avg_st"] < 0.14) & (df["rank_score"] >= 3)
  ).any()
  df["outer_follow_advantage"] = df.apply(
      lambda r: 1.5 if (is_boat4_strong and r["entry_course"] == 5) else 1.0,
      axis=1,
  )

  return df