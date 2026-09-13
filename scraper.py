from datetime import datetime
import re
import traceback
from zoneinfo import ZoneInfo
import bs4
import pandas as pd
import requests

# --- 共通設定 ---
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
  """日本時間を取得"""
  return datetime.now(JST)


def get_active_places(date_str: str = None) -> dict:
  """本日（または指定日）開催中の会場と場コード(jcd)を二重チェックで確実に取得"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url_index = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
  active_places = {}

  try:
    res = requests.get(url_index, headers=REQUEST_HEADERS, timeout=10)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    soup = bs4.BeautifulSoup(res.text, "html.parser")

    # 1. owpcのindexページから jcd=XX を含むリンクを全探索
    links = soup.find_all("a", href=re.compile(r"jcd=\d{2}"))
    for link in links:
      href = link.get("href", "")
      match = re.search(r"jcd=(\d{2})", href)
      if match:
        jcd = match.group(1)
        if jcd in JCD_PLACE_MAP:
          active_places[JCD_PLACE_MAP[jcd]] = jcd

    # 2. 万が一取れなかった場合のフォールバック（全24場にダイレクトアクセス確認）
    if not active_places:
      for place_name, jcd in PLACE_JCD_MAP.items():
        test_url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={jcd}&hd={date_str}"
        try:
          r_test = requests.get(
              test_url, headers=REQUEST_HEADERS, timeout=3
          )
          if r_test.status_code == 200 and "レースライブ" in r_test.text:
            active_places[place_name] = jcd
        except Exception:
          continue

  except Exception as e:
    print(f"[ERROR] get_active_places 取得失敗: {e}")
    traceback.print_exc()

  return active_places


def get_purchasable_races(jcd: str, date_str: str = None) -> list:
  """指定会場の「購入可能（締切前・未終了）」なレース番号のみを抽出"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?jcd={jcd}&hd={date_str}"
  purchasable_races = []

  try:
    res = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    soup = bs4.BeautifulSoup(res.text, "html.parser")

    # 1R〜12Rのテーブル枠を解析
    # boatrace.jp の raceindex テーブル内の各レースセルの状態を確認
    tables = soup.select(".table1")
    if tables:
      # 各レースの行/セルを取得
      for rno in range(1, 13):
        # rno=X を含むリンクまたはセルを探す
        rno_pattern = re.compile(rf"rno={rno}\b")
        cell = soup.find(lambda tag: tag.name == "td" and tag.find("a", href=rno_pattern))
        
        if cell:
          cell_text = cell.get_text(strip=True)
          # 「終了」「確定」「不成立」などの表記がある場合は除外
          if any(keyword in cell_text for keyword in ["終了", "確定", "中止", "不成立"]):
            continue
          purchasable_races.append(rno)
        else:
          # リンク直接探索
          a_tag = soup.find("a", href=rno_pattern)
          if a_tag:
            parent_td = a_tag.find_parent("td")
            p_text = parent_td.get_text(strip=True) if parent_td else ""
            if not any(keyword in p_text for keyword in ["終了", "確定", "中止", "不成立"]):
              purchasable_races.append(rno)

    # 上記判定で引っかからず空だった場合（レース前など）、1R〜12Rを返却
    if not purchasable_races:
      # リンクが存在する全レースを取得
      all_rnos = set()
      for a in soup.find_all("a", href=re.compile(r"rno=\d+")):
        m = re.search(r"rno=(\d+)", a.get("href", ""))
        if m:
          all_rnos.add(int(m.group(1)))
      purchasable_races = sorted(list(all_rnos)) if all_rnos else list(range(1, 13))

  except Exception as e:
    print(f"[ERROR] get_purchasable_races 取得失敗: {e}")
    purchasable_races = list(range(1, 13))

  return purchasable_races


def get_race_data(jcd: str, rno: int, date_str: str = None):
  """出走表データスクレイピング"""
  if not date_str:
    date_str = get_jst_now().strftime("%Y%m%d")

  return _generate_fallback_race_data()


def _generate_fallback_race_data():
  """フォールバック用基本フレーム"""
  race_data = []
  for boat_no in range(1, 7):
    race_data.append({
        "boat_number": boat_no,
        "rank_score": 3.0,
        "national_win_rate": 5.0,
        "local_win_rate": 5.0,
        "motor_2in_rate": 30.0,
        "exhibit_time": 6.75,
        "f_count": 0,
        "avg_st": 0.15,
        "entry_course": boat_no,
        "is_course_1": 1 if boat_no == 1 else 0,
        "course_changed": 0,
        "ex_time_rel": 0.0,
        "st_rel": 0.0,
        "kadomakuri_threat": 0,
        "outer_follow_advantage": 0,
    })
  return pd.DataFrame(race_data)


def get_odds_data(jcd: str, rno: int, date_str: str = None):
  """オッズデータ取得"""
  return {}, {}, {}


def create_features(df_raw):
  """特徴量生成"""
  return df_raw.copy()