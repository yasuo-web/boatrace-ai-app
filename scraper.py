import time
from bs4 import BeautifulSoup
import pandas as pd
import requests


def get_race_data(jcd: str, rno: int, date_str: str) -> pd.DataFrame:
  """指定された場コード(jcd)、レース番号(rno)、日付(date_str: YYYYMMDD)の出走表を取得する関数"""
  url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd:02s}&hd={date_str}"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  res = requests.get(url, headers=headers)
  res.encoding = res.apparent_encoding

  if res.status_code != 200:
      return None

  soup = BeautifulSoup(res.text, "html.parser")

  # 出走表テーブルの取得
  tables = soup.find_all("table", class_="is-w780")
  if not tables:
      return None

  rows = tables[0].find_all("tbody")
  race_data = []

  for i, row in enumerate(rows, start=1):
      # 各艇の情報セルをパース（サイト構造に合わせ抽出）
      cols = row.find_all("td")
      if len(cols) < 4:
          continue

      # 全国勝率・モータ率のテキスト抽出
      # ※公式HTML構造から該当する文字列を取り出す処理
      try:
          # 勝率データなどのセルから数値を抽出（簡易抽出例）
          rates_text = cols[4].get_text(strip=True)
          nat_win = float(rates_text.split("%")[0]) if "%" in rates_text else 5.0
      except Exception:
          nat_win = 5.0  # パース失敗時のデフォルト

      race_data.append({
          "boat_number": i,
          "national_win_rate": nat_win,
          "local_win_rate": nat_win,
          "motor_2in_rate": 30.0,  # 同様にパースして取得可能
          "exhibit_time": 6.70,  # 直前情報ページから別途取得も可能
      })

  time.sleep(1)  # サーバー負荷軽減のため必須
  return pd.DataFrame(race_data)