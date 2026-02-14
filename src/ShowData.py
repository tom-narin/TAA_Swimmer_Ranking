import streamlit as st
import pandas as pd
import os
from datawebtaa import SwimDataScraper  # Import your existing class

# --- Page Configuration ---
st.set_page_config(page_title="TAA's Swimming Analytics", layout="wide", page_icon="🏊")

# Custom CSS for a professional look
st.markdown("""
    <style>
    /* Make the buttons look like a professional sports app */
    .stButton>button {
        width: 100%;
        background-color: #004a99; /* TAA Blue */
        color: white;
        border-radius: 10px;
        border: none;
        transition: 0.3s;
        height: 3em;
    }
    .stButton>button:hover {
        background-color: #003366;
        border: 1px solid white;
    }
    /* Improve the table look */
    .stDataFrame {
        border: 1px solid #e6e9ef;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def time_to_seconds(time_str):
    """Converts MM:SS.ss or SS.ss to total seconds."""
    try:
        if not isinstance(time_str, str) or not time_str.strip():
            return float('inf')
        parts = time_str.split(':')
        if len(parts) == 2: # MM:SS.ss
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1: # SS.ss
            return float(parts[0])
        return float('inf')
    except:
        return float('inf')

# --- Main Dashboard ---
st.title("🏊 TAA Performance Dashboard")

# --- Input Parameters at the Top ---
with st.container():
    st.subheader("📋 Search Parameters")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stroke_key = st.selectbox("Stroke Type", options=list(SwimDataScraper.STROKES.keys()), 
                                         format_func=lambda x: SwimDataScraper.STROKES[x]['name'])
    with c2:
        dist_key = st.selectbox("Distance", options=list(SwimDataScraper.DISTANCES.keys()), 
                                       format_func=lambda x: SwimDataScraper.DISTANCES[x]['name'])
    with c3:
        gender_key = st.selectbox("Gender", options=list(SwimDataScraper.GENDERS.keys()), 
                                         format_func=lambda x: SwimDataScraper.GENDERS[x]['name'])
    with c4:
        pool_key = st.selectbox("Pool Type", options=list(SwimDataScraper.POOL_TYPES.keys()), 
                                       format_func=lambda x: SwimDataScraper.POOL_TYPES[x]['name'])

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        min_age = st.number_input("Min Age", value=9)
    with c6:
        max_age = st.number_input("Max Age", value=9)
    with c7:
        swimmer_time_input = st.text_input("Compare Swimmer Time (MM:SS.ss)", value="00:00.00")
    with c8:
        st.write("") # Spacer
        fetch_button = st.button("🔍 Fetch Latest Rankings")

st.markdown(f"Currently tracking ** {SwimDataScraper.GENDERS[gender_key]['name']} ** Stroke ** {SwimDataScraper.STROKES[stroke_key]['name']}** at **{SwimDataScraper.DISTANCES[dist_key]['name']}**")

if fetch_button or 'current_df' in st.session_state:
    if fetch_button:
        # Initialize your existing scraper class
        scraper = SwimDataScraper(headless=True)
        
        with st.spinner("Connecting to Thailand Aquatics Database..."):
            # Use your existing class methods
            df = scraper.scrape_rankings(
                SwimDataScraper.STROKES[stroke_key],
                SwimDataScraper.DISTANCES[dist_key],
                SwimDataScraper.GENDERS[gender_key],
                SwimDataScraper.POOL_TYPES[pool_key],
                str(min_age),
                str(max_age)
            )
            scraper.close()
            st.session_state.current_df = df
    else:
        df = st.session_state.current_df

    if df is not None and not df.empty:
        # --- Time Difference Logic ---
        top_time_str = df['Time'].iloc[0]
        top_seconds = time_to_seconds(top_time_str)
        
        # Calculate 'Time Diff' relative to Rank #1
        df['Seconds'] = df['Time'].apply(time_to_seconds)
        df['Time Diff'] = df['Seconds'].apply(lambda x: f"+{x - top_seconds:.2f}s" if x > top_seconds else "-")
        
        # Reorder columns: Move 'Time Diff' after 'Time'
        cols = list(df.columns)
        # Assuming your scraper generates: ['Rank', 'Name', 'Club', 'Nationality', 'Time', ...]
        time_idx = cols.index('Time')
        cols.insert(time_idx + 1, cols.pop(cols.index('Time Diff')))
        df = df[cols]
        
        # --- Analytics Header ---
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("Total Competitors", len(df))
        with m_col2:
            st.metric("Top Time (Rank #1)", top_time_str)
        with m_col3:
            # Comparison Logic for Input Time
            input_seconds = time_to_seconds(swimmer_time_input)
            if input_seconds > 0 and input_seconds != float('inf'):
                potential_rank = len(df[df['Seconds'] < input_seconds]) + 1
                diff_to_top = input_seconds - top_seconds
                diff_str = f"(+{diff_to_top:.2f}s from Top)" if diff_to_top > 0 else "(New Rank #1!)"
                st.metric("Your Potential Rank", f"#{potential_rank}", delta=diff_str, delta_color="inverse")
            else:
                st.metric("Your Potential Rank", "N/A")

        # --- Data View ---
        st.subheader("Interactive Ranking Table")
        # Drop helper columns before showing
        display_df = df.drop(columns=['Seconds'], errors='ignore')
        st.dataframe(display_df, use_container_width=True, height=500)

        # --- Export Logic ---
        st.divider()
        csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 Download Portfolio-Ready CSV",
            data=csv_data,
            file_name=f"TAA_Ranking_Age{min_age}_{stroke_key}.csv",
            mime='text/csv'
        )
    else:
        if fetch_button:
            st.warning("No data found for these parameters. Try adjusting the age or date range.")

else:
    st.info("Select parameters and click 'Fetch Latest Rankings' to begin data extraction.")
