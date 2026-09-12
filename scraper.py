import time
import re
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
            # 全国勝率
            rates_text = cols[4].get_text(strip=True)
            nat_win = float(rates_text.split("%")[0]) if "%" in rates_text else 5.0
            
            # F数・平均STの抽出（簡易パース例）
            st_text = cols[3].get_text(strip=True)
            f_count = 1 if "F1" in st_text else (2 if "F2" in st_text else 0)
            
            # 平均ST（数字部分を抽出）
            st_match = re.search(r'0\.\d+', st_text)
            avg_st = float(st_match.group(0)) if st_match else 0.17
            
        except Exception:
            nat_win = 5.0
            f_count = 0
            avg_st = 0.17
            
        race_data.append({
            "boat_number": i,
            "national_win_rate": nat_win,
            "local_win_rate": nat_win,
            "motor_2in_rate": 30.0,
            "exhibit_time": 6.70,
            "f_count": f_count,      # 新規追加
            "avg_st": avg_st,        # 新規追加
        })
        
    time.sleep(1)
    return pd.DataFrame(race_data)

def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """共通の特徴量作成関数"""
    df = df.copy()
    
    # 1. フラグ系
    df["is_boat_1"] = (df["boat_number"] == 1).astype(int)
    df["has_flying"] = (df["f_count"] > 0).astype(int)
    
    # 2. 組み合わせ（1号艇 × F持ち = 飛ばしやすい危険フラグ）
    df["boat1_and_flying"] = df["is_boat_1"] * df["has_flying"]
    
    # 3. レース内相対値（展示タイム差、ST差）
    df["ex_time_rel"] = df["exhibit_time"] - df["exhibit_time"].mean()
    df["st_rel"] = df["avg_st"] - df["avg_st"].mean()
    
    return df