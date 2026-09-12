from datetime import datetime
import re
import time
from bs4 import BeautifulSoup
import pandas as pd
import requests

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


def get_active_places(date_str: str) -> dict:
  """本日開催されている会場一覧を取得 {会場名: jcd}"""
  url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  active_places = {}
  try:
    res = requests.get(url, headers=headers, timeout=10)
    res.encoding = res.apparent_encoding
    if res.status_code != 200:
      return active_places

    soup = BeautifulSoup(res.text, "html.parser")
    links = soup.find_all(
        "a", href=re.compile(r"/owpc/pc/race/raceindex\?jcd=")
    )

    for link in links:
      match = re.search(r"jcd=(\d{2})", link["href"])
      if match:
        jcd = match.group(1)
        if jcd in JCD_MAP:
          active_places[JCD_MAP[jcd]] = jcd
  except Exception:
    pass

  return active_places


def get_purchasable_races(jcd: str, date_str: str) -> list:
  """指定会場の「現在時刻より締切が未来のレース（購入可能）」リストを取得"""
  url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={jcd}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  purchasable_races = []
  try:
    res = requests.get(url, headers=headers, timeout=10)
    res.encoding = res.apparent_encoding
    if res.status_code != 200:
      return [i for i in range(1, 13)]

    soup = BeautifulSoup(res.text, "html.parser")
    now = datetime.now()

    tables = soup.find_all("table", class_="is-w780")
    for table in tables:
      rows = table.find_all("tr")
      for row in rows:
        text = row.get_text(strip=True)
        matches = re.findall(r"(\d{1,2})R\s*(\d{1,2}:\d{2})", text)
        for rno_str, time_str in matches:
          try:
            rno = int(rno_str)
            limit_time = datetime.strptime(
                f"{date_str} {time_str}", "%Y%m%d %H:%M"
            )
            if now < limit_time:
              if rno not in purchasable_races:
                purchasable_races.append(rno)
          except Exception:
            continue
  except Exception:
    pass

  return (
      sorted(purchasable_races) if purchasable_races else [i for i in range(1, 13)]
  )


def get_race_data(jcd: str, rno: int, date_str: str) -> pd.DataFrame:
  """出走表・選手・展示データの取得"""
  url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd:02s}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  try:
    res = requests.get(url, headers=headers, timeout=10)
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
  except Exception:
    return None


def get_odds_data(jcd: str, rno: int, date_str: str) -> dict:
  """3連単オッズデータをスクレイピング取得"""
  url = f"https://www.boatrace.jp/owpc/pc/race/odds3t?rno={rno}&jcd={jcd:02s}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  odds_dict = {}
  try:
    res = requests.get(url, headers=headers, timeout=10)
    res.encoding = res.apparent_encoding
    if res.status_code != 200:
      return odds_dict

    soup = BeautifulSoup(res.text, "html.parser")
    tables = soup.find_all("table", class_="is-w780")

    for table in tables:
      rows = table.find_all("tr")
      for row in rows:
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