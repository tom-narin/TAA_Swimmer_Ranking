import streamlit as st
import pandas as pd
from datetime import date, timedelta
from datawebtaa import SwimDataScraper

st.set_page_config(page_title="TAA Analytics", layout="wide")

def main():
    st.title("🏊 TAA Ranking Analytics")
    
    with st.sidebar:
        st.header("Debug Console")
        debug_log = st.empty()

    with st.container():
        col1, col2, col3, col4 = st.columns(4)
        with col1: stroke = st.selectbox("Stroke", list(SwimDataScraper.STROKES.keys()), format_func=lambda x: SwimDataScraper.STROKES[x]['name'])
        with col2: dist = st.selectbox("Distance", list(SwimDataScraper.DISTANCES.keys()), format_func=lambda x: SwimDataScraper.DISTANCES[x]['name'])
        with col3: gender = st.selectbox("Gender", list(SwimDataScraper.GENDERS.keys()), format_func=lambda x: SwimDataScraper.GENDERS[x]['name'])
        with col4: pool = st.selectbox("Pool", list(SwimDataScraper.POOL_TYPES.keys()), format_func=lambda x: SwimDataScraper.POOL_TYPES[x]['name'])
        
        col5, col6, col7 = st.columns([1,1,2])
        with col5: min_age = st.number_input("Min Age", 5, 90, 10)
        with col6: max_age = st.number_input("Max Age", 5, 90, 11)
        with col7:
            today = date.today()
            one_year_ago = today - timedelta(days=365)
            date_range = st.date_input("Date Range (dd/mmm/yy)", value=(one_year_ago, today))
            start_d = date_range[0]
            end_d = date_range[1] if len(date_range) > 1 else today
            st.caption(f"Selected: {start_d.strftime('%d/%b/%y')} to {end_d.strftime('%d/%b/%y')}")

    if st.button("🚀 Fetch Rankings"):
        scraper = SwimDataScraper(headless=True)
        with st.status("Fetching Data...", expanded=True) as status:
            st.write(f"DEBUG: Applying filter {start_d} to {end_d}")
            df = scraper.scrape_rankings(
                SwimDataScraper.STROKES[stroke], 
                SwimDataScraper.DISTANCES[dist],
                SwimDataScraper.GENDERS[gender],
                SwimDataScraper.POOL_TYPES[pool],
                str(min_age), str(max_age), start_d, end_d
            )
            status.update(label="Complete!", state="complete")
        
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No records found.")
        scraper.close()

if __name__ == "__main__":
    main()
