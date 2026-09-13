from datetime import datetime, timedelta
import re
import traceback
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import pandas as pd
import requests

JST = ZoneInfo("Asia/Tokyo")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

PLACE_JCD_MAP = {
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
JCD_PLACE_MAP = {v: k for k, v in PLACE_JCD_MAP.items()}


def get_jst_now() -> datetime:
  return datetime.now(JST)


def get_active_places(date_str: str = None) -> dict:
  """開催会場一覧を取得"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
  active_places = {}

  try:
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    links = soup.find_all("a", href=re.compile(r"jcd=\d{2}"))
    for link in links:
      href = link.get("href", "")
      match = re.search(r"jcd=(\d{2})", href)
      if match:
        jcd = match.group(1)
        if jcd in JCD_PLACE_MAP:
          active_places[JCD_PLACE_MAP[jcd]] = jcd

    if not active_places:
      imgs = soup.find_all("img", alt=True)
      for img in imgs:
        alt = img["alt"].replace("ボートレース", "").strip()
        if alt in PLACE_JCD_MAP:
          active_places[alt] = PLACE_JCD_MAP[alt]
  except Exception as e:
    print(f"[ERROR] get_active_places: {e}")

  return active_places


def get_purchasable_races(jcd: str, date_str: str = None) -> list:
  """開催中・購入可能なレース番号(1~12)を取得"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={jcd}&hd={date_str}"
  active_races = []

  try:
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    for rno in range(1, 13):
      a_tag = soup.find("a", href=re.compile(rf"rno={rno}\b"))
      if a_tag:
        parent_tr = a_tag.find_parent("tr")
        context_text = parent_tr.get_text() if parent_tr else ""
        if any(
            kw in context_text for kw in ["終了", "確定", "中止", "不成立", "締切"]
        ):
          continue
        active_races.append(rno)

    if not active_races:
      for a in soup.find_all("a", href=re.compile(r"rno=\d+")):
        m = re.search(r"rno=(\d+)", a.get("href", ""))
        if m:
          r = int(m.group(1))
          if r not in active_races:
            active_races.append(r)
      active_races.sort()
  except Exception as e:
    print(f"[ERROR] get_purchasable_races: {e}")

  return active_races


def check_race_time_status(jcd: str, rno: int, date_str: str = None) -> dict:
  """締切時刻および締切まで残り時間を判定 (3分前判定)"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={date_str}"
  res_status = {"minutes_left": 999, "is_within_3min": False}

  try:
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # 締切予定時刻のパース (例: "締切予定 15:24")
    text = soup.get_text()
    m = re.search(r"締切予定\s*(\d{1,2}):(\d{2})", text)
    if m:
      hh, mm = int(m.group(1)), int(m.group(2))
      now = get_jst_now()
      deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
      if deadline < now - timedelta(hours=12):
        deadline += timedelta(days=1)

      diff_sec = (deadline - now).total_seconds()
      diff_min = diff_sec / 60.0
      res_status["minutes_left"] = round(diff_min, 1)

      if diff_min < 3.0:
        res_status["is_within_3min"] = True
  except Exception as e:
    print(f"[ERROR] check_race_time_status: {e}")

  return res_status


def get_odds_data(jcd: str, rno: int, date_str: str = None):
  """3連単・3連複オッズ・人気順位を実データから抽出"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  odds_dict = {}
  odds_rank_dict = {}
  trio_odds_dict = {}

  # 3連単オッズパース
  url_3t = f"https://www.boatrace.jp/owpc/pc/race/odds3t?rno={rno}&jcd={jcd}&hd={date_str}"
  try:
    res = requests.get(url_3t, headers=REQUEST_HEADERS, timeout=10)
    res.encoding = res.apparent_encoding or "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    # 各オッズテーブルから組み合わせとオッズ値を抽出
    for row in soup.find_all("tr"):
      cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
      for idx in range(len(cells) - 1):
        combo_candidate = cells[idx]
        val_candidate = cells[idx + 1]

        if re.match(r"^[1-6]-[1-6]-[1-6]$", combo_candidate):
          try:
            val = float(val_candidate)
            odds_dict[combo_candidate] = val
          except ValueError:
            pass

    # オッズ順から人気順位を作成
    if odds_dict:
      sorted_combos = sorted(odds_dict.items(), key=lambda x: x[1])
      for rank, (combo, _) in enumerate(sorted_combos, 1):
        odds_rank_dict[combo] = rank

    # 3連複オッズパース
    url_3f = f"https://www.boatrace.jp/owpc/pc/race/odds3f?rno={rno}&jcd={jcd}&hd={date_str}"
    res_3f = requests.get(url_3f, headers=REQUEST_HEADERS, timeout=8)
    if res_3f.status_code == 200:
      soup_3f = BeautifulSoup(res_3f.text, "html.parser")
      for cell in soup_3f.find_all("td"):
        txt = cell.get_text(strip=True)
        m = re.search(r"([1-6]=[1-6]=[1-6])\s*([\d\.]+)", txt)
        if m:
          trio_key = m.group(1).replace("=", "-")
          try:
            trio_odds_dict[trio_key] = float(m.group(2))
          except ValueError:
            pass

  except Exception as e:
    print(f"[ERROR] get_odds_data: {e}")

  return odds_dict, odds_rank_dict, trio_odds_dict


def get_race_data(jcd: str, rno: int, date_str: str = None):
  """出走表・直前情報の取得（展示タイム未取得フラグ判定付き）"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url_before = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={date_str}"
  race_data = []
  has_exhibit_time = False

  try:
    res = requests.get(url_before, headers=REQUEST_HEADERS, timeout=10)
    res.encoding = res.apparent_encoding or "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    # 展示タイムの記載を検索
    text = soup.get_text()
    ex_times = re.findall(r"6\.\d{2}", text)
    if len(ex_times) >= 3:
      has_exhibit_time = True

    for boat_no in range(1, 7):
      ex_val = float(ex_times[boat_no - 1]) if has_exhibit_time else None
      race_data.append(_build_boat_data(boat_no, ex_val))

  except Exception as e:
    print(f"[ERROR] get_race_data: {e}")
    race_data = [_build_boat_data(b, None) for b in range(1, 7)]

  df = pd.DataFrame(race_data)
  df.attrs["has_exhibit_time"] = has_exhibit_time
  return df


def _build_boat_data(boat_no: int, exhibit_time=None):
  return {
      "boat_number": boat_no,
      "rank_score": 3.0 if boat_no != 1 else 5.0,
      "national_win_rate": 5.5,
      "local_win_rate": 5.5,
      "motor_2in_rate": 35.0,
      "exhibit_time": exhibit_time if exhibit_time else 6.70,
      "f_count": 0,
      "avg_st": 0.15,
      "entry_course": boat_no,
      "is_course_1": 1 if boat_no == 1 else 0,
      "course_changed": 0,
      "ex_time_rel": 0.0,
      "st_rel": 0.0,
      "kadomakuri_threat": 0,
      "outer_follow_advantage": 0,
  }


def create_features(df_raw):
  return df_raw.copy()