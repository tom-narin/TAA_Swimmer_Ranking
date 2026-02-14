import streamlit as st
import pandas as pd
from datetime import date, timedelta
from datawebtaa import SwimDataScraper

st.set_page_config(page_title="TAA Ranking Analytics", layout="wide")

def main():
    st.title("🏊 Thailand Aquatics Ranking Analytics")
    
    # Session state for log messages to display in UI
    if 'debug_logs' not in st.session_state:
        st.session_state.debug_logs = []

    with st.container():
        col1, col2, col3, col4 = st.columns(4)
        with col1: stroke_k = st.selectbox("Stroke", list(SwimDataScraper.STROKES.keys()), format_func=lambda x: SwimDataScraper.STROKES[x]['name'])
        with col2: dist_k = st.selectbox("Distance", list(SwimDataScraper.DISTANCES.keys()), format_func=lambda x: SwimDataScraper.DISTANCES[x]['name'])
        with col3: gender_k = st.selectbox("Gender", list(SwimDataScraper.GENDERS.keys()), format_func=lambda x: SwimDataScraper.GENDERS[x]['name'])
        with col4: pool_k = st.selectbox("Pool", list(SwimDataScraper.POOL_TYPES.keys()), format_func=lambda x: SwimDataScraper.POOL_TYPES[x]['name'])
        
        col5, col6, col7 = st.columns([1,1,2])
        with col5: min_age = st.number_input("Min Age", 5, 90, 10)
        with col6: max_age = st.number_input("Max Age", 5, 90, 11)
        with col7:
            # Calculation for Now - 1 Year
            today = date.today()
            one_year_ago = today - timedelta(days=365)
            
            # Use columns for date range to handle formatting
            date_range = st.date_input(
                "Select Date Range (Start - End)",
                value=(one_year_ago, today),
                help="Defaults to last 365 days"
            )
            
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
            else:
                start_d = date_range[0] if isinstance(date_range, (tuple, list)) else date_range
                end_d = today
                
            st.caption(f"Search window: **{start_d.strftime('%d %b %Y')}** to **{end_d.strftime('%d %b %Y')}**")

    if st.button("🚀 Fetch Rankings"):
        scraper = SwimDataScraper(headless=True)
        try:
            with st.status("Initializing Scraper...", expanded=True) as status:
                st.write(f"Applying filter: {start_d} to {end_d}")
                df = scraper.scrape_rankings(
                    SwimDataScraper.STROKES[stroke_k], 
                    SwimDataScraper.DISTANCES[dist_k],
                    SwimDataScraper.GENDERS[gender_k],
                    SwimDataScraper.POOL_TYPES[pool_k],
                    str(min_age), str(max_age), 
                    start_d, end_d
                )
                
                if df is not None:
                    status.update(label=f"Fetched {len(df)} records!", state="complete", expanded=False)
                    if not df.empty:
                        st.success(f"Successfully retrieved {len(df)} swimmers.")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.warning("The search returned no results. Try adjusting the age or date range.")
                else:
                    status.update(label="Scraping Failed", state="error")
                    st.error("An error occurred during scraping. Check logs for details.")
        finally:
            scraper.close()

if __name__ == "__main__":
    main()
