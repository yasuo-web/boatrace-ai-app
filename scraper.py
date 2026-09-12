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
  url = (
      f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
  )
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  res = requests.get(url, headers=headers)
  res.encoding = res.apparent_encoding
  active_places = {}

  if res.status_code != 200:
    return active_places

  soup = BeautifulSoup(res.text, "html.parser")
  links = soup.find_all("a", href=re.compile(r"/owpc/pc/race/raceindex\?jcd="))

  for link in links:
    match = re.search(r"jcd=(\d{2})", link["href"])
    if match:
      jcd = match.group(1)
      if jcd in JCD_MAP:
        active_places[JCD_MAP[jcd]] = jcd

  return active_places


def get_purchasable_races(jcd: str, date_str: str) -> list:
  """指定会場の「現在時刻より締切が未来のレース（購入可能）」リストを取得"""
  url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={jcd}&hd={date_str}"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  res = requests.get(url, headers=headers)
  res.encoding = res.apparent_encoding
  purchasable_races = []

  if res.status_code != 200:
    return [i for i in range(1, 13)]  # 取得失敗時はフォールバック

  soup = BeautifulSoup(res.text, "html.parser")
  now = datetime.now()

  # 1R〜12Rの締切時刻（電話投票締切）を取得
  tables = soup.find_all("table", class_="is-w780")
  for table in tables:
    rows = table.find_all("tr")
    for row in rows:
      cols = row.find_all(["td", "th"])
      text = row.get_text(strip=True)

      # レース番号と締切時刻（例: "1R 10:35" 形式）の抽出
      matches = re.findall(r"(\d{1,2})R\s*(\d{1,2}:\d{2})", text)
      for rno_str, time_str in matches:
        try:
          rno = int(rno_str)
          limit_time = datetime.strptime(
              f"{date_str} {time_str}", "%Y%m%d %H:%M"
          )
          # 現在時刻が締切時刻前であれば対象
          if now < limit_time:
            if rno not in purchasable_races:
              purchasable_races.append(rno)
        except Exception:
          continue

  # 万が一締切データがパースできなかった場合は全レースを返す
  return (
      sorted(purchasable_races) if purchasable_races else [i for i in range(1, 13)]
  )


# --- 既存の get_race_data, get_odds_data, create_features はそのまま保持 ---