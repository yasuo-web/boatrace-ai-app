import os
import json
import pandas as pd
import streamlit as st
import lightgbm as lgb
from datetime import datetime

st.set_page_config(page_title="競艇予測システム", layout="wide")

st.title("競艇 AI予測ダッシュボード")

# タブ切り替え（リアルタイム/サンプル表示 ⇔ 過去検証）
tab1, tab2 = st.tabs(["🎯 リアルタイム/サンプル予測", "📜 過去検証"])

# ------------------------------------------------------------------
# Tab 1: 通常のリアルタイム・サンプルデータ表示
# ------------------------------------------------------------------
with tab1:
    st.header("最新レース予測結果")
    
    # latest_predictions.json の読み込みと表示
    if os.path.exists("latest_predictions.json"):
        with open("latest_predictions.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        st.caption(f"最終更新日時: {data.get('updated_at', '不明')}")
        
        # 上位5点 ＆ 万舟表示等のメインUI処理
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 買い目 上位5点")
            # データの表示処理
            st.dataframe(pd.DataFrame(data.get("top_predictions", [])))
            
        with col2:
            st.subheader("💰 万舟フラグ（100倍以上）")
            st.dataframe(pd.DataFrame(data.get("high_odds_predictions", [])))
    else:
        st.info("現在利用可能な最新予測データがありません。サンプルデータを表示します。")
        # サンプルデータ処理

# ------------------------------------------------------------------
# Tab 2: 過去検証機能
# ------------------------------------------------------------------
with tab2:
    st.header("過去データ検証（バックテスト）")
    
    col_date, col_place, col_race = st.columns(3)
    
    with col_date:
        target_date = st.date_input("検証対象日", value=datetime.today())
    with col_place:
        # 全24会場選択
        stadiums = [
            "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖", 
            "蒲郡", "常滑", "津", "三国", "びわこ", "住之江", 
            "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山", 
            "下関", "若松", "芦屋", "福岡", "唐津", "大村"
        ]
        selected_stadium = st.selectbox("会場", stadiums)
    with col_race:
        selected_race = st.selectbox("レース番号", [f"{i}R" for i in range(1, 13)])

    if st.button("過去検証を実行"):
        date_str = target_date.strftime("%Y-%m-%d")
        st.write(f"**【検証条件】** {date_str} / {selected_stadium} / {selected_race}")
        
        # 過去ログファイルまたはデータベースからの読み込み処理
        history_file = f"history/{date_str}.json"
        
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
            
            # 該当レースの抽出と照合表示
            target_key = f"{selected_stadium}_{selected_race}"
            if target_key in hist_data:
                res = hist_data[target_key]
                
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("🤖 AI予測結果")
                    st.table(pd.DataFrame(res.get("predictions", [])))
                with c2:
                    st.subheader("🏁 実際の確定着順・払戻")
                    st.table(pd.DataFrame(res.get("actual_results", [])))
                    st.success(f"回収結果: {res.get('payout_summary', 'データなし')}")
            else:
                st.warning("指定されたレースの検証データが見つかりませんでした。")
        else:
            st.error(f"{date_str} の過去データログが存在しません。")