import streamlit as st
import pandas as pd
import os
from datetime import date, timedelta
from datawebtaa import SwimDataScraper

# --- Page Configuration ---
st.set_page_config(page_title="TAA's Swimming Analytics", layout="wide", page_icon="🏊")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #004a99; color: white; border-radius: 10px; height: 3em; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

def time_to_seconds(time_str):
    try:
        if not isinstance(time_str, str) or not time_str.strip() or time_str == "NT":
            return float('inf')
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except: return float('inf')

def main():
    st.title("🏊 Thailand Aquatics Ranking Analytics")

    # Search Parameters
    with st.container():
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
        with c1: stroke_key = st.selectbox("Stroke", list(SwimDataScraper.STROKES.keys()), format_func=lambda x: SwimDataScraper.STROKES[x]['name'])
        with c2: dist_key = st.selectbox("Distance", list(SwimDataScraper.DISTANCES.keys()), format_func=lambda x: SwimDataScraper.DISTANCES[x]['name'])
        with c3: gender_key = st.selectbox("Gender", list(SwimDataScraper.GENDERS.keys()), format_func=lambda x: SwimDataScraper.GENDERS[x]['name'])
        with c4: pool_key = st.selectbox("Pool", list(SwimDataScraper.POOL_TYPES.keys()), format_func=lambda x: SwimDataScraper.POOL_TYPES[x]['name'])
        with c5: swimmer_time_input = st.text_input("Your Time (MM:SS.ss)", placeholder="e.g. 01:05.20")

        c6, c7, c8, c9 = st.columns([1, 1, 2, 2])
        with c6: min_age = st.number_input("Min Age", 5, 100, 10)
        with c7: max_age = st.number_input("Max Age", 5, 100, 11)
        
        # DATE LOGIC: Now and Now - 1 Year
        with c8:
            today = date.today()
            one_year_ago = today - timedelta(days=365)
            # Display format dd/mmm/yy using string formatting
            date_range = st.date_input(
                "Ranking Period (Start - End)", 
                value=(one_year_ago, today)
            )
            # Handle user only selecting one date
            start_date = date_range[0] if isinstance(date_range, tuple) else date_range
            end_date = date_range[1] if isinstance(date_range, tuple) and len(date_range) > 1 else today
            
            # Show formatted text for user confirmation
            st.caption(f"Range: {start_date.strftime('%d/%b/%y')} to {end_date.strftime('%d/%b/%y')}")

        with c9:
            st.write("")
            fetch_button = st.button("🚀 Fetch Rankings")

    if fetch_button:
        scraper = SwimDataScraper(headless=True)
        with st.spinner(f"Scraping rankings..."):
            df = scraper.scrape_rankings(
                SwimDataScraper.STROKES[stroke_key],
                SwimDataScraper.DISTANCES[dist_key],
                SwimDataScraper.GENDERS[gender_key],
                SwimDataScraper.POOL_TYPES[pool_key],
                str(min_age), str(max_age),
                start_date, end_date
            )
            scraper.close()

        if df is not None and not df.empty:
            df['Seconds'] = df['Time'].apply(time_to_seconds)
            df = df.sort_values('Seconds').reset_index(drop=True)
            df['Rank'] = range(1, len(df) + 1)

            # Metrics
            m_col1, m_col2, m_col3 = st.columns(3)
            top_time = df.iloc[0]['Time']
            top_seconds = df.iloc[0]['Seconds']
            m_col1.metric("Total Swimmers", len(df))
            m_col2.metric("Rank #1 Time", top_time)
            
            input_seconds = time_to_seconds(swimmer_time_input)
            if input_seconds < float('inf'):
                potential_rank = len(df[df['Seconds'] < input_seconds]) + 1
                m_col3.metric("Your Potential Rank", f"#{potential_rank}")

            st.dataframe(df.drop(columns=['Seconds']), use_container_width=True)
        else:
            st.warning("No data found for this selection.")

if __name__ == "__main__":
    main()
