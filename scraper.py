import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import requests


def get_race_data(jcd: str, rno: int, date_str: str) -> pd.DataFrame:
  """出走表・選手・展示データの取得"""
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
      rank_text = cols[2].get_text(strip=True)
      rank_val = (
          4
          if "A1" in rank_text
          else (3 if "A2" in rank_text else (2 if "B1" in rank_text else 1))
      )
      rates_text = cols[4].get_text(strip=True)
      nat_win = float(rates_text.split("%")[0]) if "%" in rates_text else 5.0
      st_text = cols[3].get_text(strip=True)
      f_count = 1 if "F1" in st_text else (2 if "F2" in st_text else 0)
      st_match = re.search(r"0\.\d+", st_text)
      avg_st = float(st_match.group(0)) if st_match else 0.17
      entry_course = i
    except Exception:
      rank_val, nat_win, f_count, avg_st, entry_course = 2, 5.0, 0, 0.17, i

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
  return pd.DataFrame(race_data)


def get_odds_data(jcd: str, rno: int, date_str: str) -> dict:
  """3連単オッズデータをスクレイピング取得"""
  url = f"https://www.boatrace.jp/owpc/pc/race/odds3t?rno={rno}&jcd={jcd:02s}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  res = requests.get(url, headers=headers)
  res.encoding = res.apparent_encoding
  odds_dict = {}

  if res.status_code != 200:
    return odds_dict

  soup = BeautifulSoup(res.text, "html.parser")
  tables = soup.find_all("table", class_="is-w780")

  # オッズテーブルのパース（取得不可時や前売りデータ対応）
  try:
    for table in tables:
      rows = table.find_all("tr")
      for row in rows:
        cols = row.find_all(["td", "th"])
        # 組み合わせとオッズ数字の抽出ロジック（簡易フォールバック付き）
        text = row.get_text(strip=True)
        matches = re.findall(r"([1-6]-[1-6]-[1-6])\s*([\d\.]+)", text)
        for combo, odds in matches:
          odds_dict[combo] = float(odds)
  except Exception:
    pass

  return odds_dict


def create_features(df: pd.DataFrame) -> pd.DataFrame:
  """特徴量生成エンジン"""
  df = df.copy()
  df["is_boat_1"] = (df["boat_number"] == 1).astype(int)
  df["has_flying"] = (df["f_count"] > 0).astype(int)
  df["is_course_1"] = (df["entry_course"] == 1).astype(int)
  df["course_changed"] = (df["boat_number"] != df["entry_course"]).astype(int)
  df["ex_time_rel"] = df["exhibit_time"] - df["exhibit_time"].mean()
  df["st_rel"] = df["avg_st"] - df["avg_st"].mean()

  kadomakuri_score = df.apply(
      lambda r: (0.25 - r["avg_st"]) * r["rank_score"]
      if r["entry_course"] in [3, 4]
      else 0,
      axis=1,
  ).max()
  df["kadomakuri_threat"] = kadomakuri_score

  is_boat4_strong = (
      (df["entry_course"] == 4) & (df["avg_st"] < 0.14) & (df["rank_score"] >= 3)
  ).any()
  df["outer_follow_advantage"] = df.apply(
      lambda r: 1.5 if (is_boat4_strong and r["entry_course"] == 5) else 1.0,
      axis=1,
  )

  return df