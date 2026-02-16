import streamlit as st
import pandas as pd
from datetime import date, timedelta
from datawebtaa import SwimDataScraper
from datawebtaa_ajax import SwimDataAjaxScraper
import database as db

st.set_page_config(page_title="TAA Ranking Analytics", layout="wide")

def parse_age_range(age_str):
    if not isinstance(age_str, str):
        return None, None
    if '-' in age_str:
        try:
            parts = age_str.split('-')
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return None, None
    else:
        try:
            age = int(age_str)
            return age, age
        except ValueError:
            return None, None

THAI_MONTH_MAP = {
    'ม.ค.': 'Jan', 'ก.พ.': 'Feb', 'มี.ค.': 'Mar', 'เม.ย.': 'Apr', 'พ.ค.': 'May',
    'มิ.ย.': 'Jun', 'ก.ค.': 'Jul', 'ส.ค.': 'Aug', 'ก.ย.': 'Sep', 'ต.ค.': 'Oct',
    'พ.ย.': 'Nov', 'ธ.ค.': 'Dec'
}

def parse_thai_date(date_str):
    if not isinstance(date_str, str):
        return pd.NaT
    try:
        day, thai_month_abbr, buddhist_year_str = date_str.split('/')
        buddhist_year = int(buddhist_year_str)
        english_month_abbr = THAI_MONTH_MAP.get(thai_month_abbr.strip())
        if english_month_abbr:
            gregorian_year = buddhist_year - 543
            standard_date_str = f"{day}-{english_month_abbr}-{gregorian_year}"
            return pd.to_datetime(standard_date_str, format='%d-%b-%Y', errors='coerce')
    except (ValueError, KeyError, IndexError):
        pass
    return pd.NaT

def format_date_to_thai_buddhist(date_obj):
    if not isinstance(date_obj, date):
        return None
    buddhist_year = date_obj.year + 543
    thai_month_abbr_reverse_map = {v: k for k, v in THAI_MONTH_MAP.items()}
    english_month_abbr = date_obj.strftime('%b')
    thai_month = thai_month_abbr_reverse_map.get(english_month_abbr)
    if thai_month:
        return f"{date_obj.day}/{thai_month}/{buddhist_year}"
    return None

def add_record_page():
    st.header("📝 Add a New Swim Record")
    # Initialize session state variables
    for key in ['manual_swimmer_search', 'manual_selected_swimmer', 'manual_competition_search', 'manual_selected_competition']:
        if key not in st.session_state:
            st.session_state[key] = "" if 'search' in key else None

    # --- 1. Swimmer Selection ---
    st.subheader("1. Find or Add Swimmer")
    swimmer_search_term = st.text_input("Search Swimmer Name", st.session_state.manual_swimmer_search, key='swimmer_search_input')
    if swimmer_search_term != st.session_state.manual_swimmer_search:
        st.session_state.manual_swimmer_search = swimmer_search_term
        st.session_state.manual_selected_swimmer = None
        st.rerun()

    prefilled_name, prefilled_gender, prefilled_club, prefilled_school = st.session_state.manual_swimmer_search, None, "", ""
    if st.session_state.manual_selected_swimmer:
        swimmer_data = db.get_swimmer_by_name(st.session_state.manual_selected_swimmer)
        if swimmer_data is not None:
            prefilled_name, prefilled_gender, prefilled_club, prefilled_school = swimmer_data['Name'], swimmer_data['Gender'], swimmer_data['Club'], swimmer_data['School']

    if st.session_state.manual_swimmer_search:
        swimmer_results = db.search_swimmers(st.session_state.manual_swimmer_search)
        if not swimmer_results.empty:
            swimmer_options = [f"Add '{st.session_state.manual_swimmer_search}' as new swimmer"] + swimmer_results['Name'].tolist()
            selected_option = st.radio("Select a swimmer or confirm new:", swimmer_options, key="swimmer_select_radio")
            if "Add '" not in selected_option and st.session_state.manual_selected_swimmer != selected_option:
                st.session_state.manual_selected_swimmer = selected_option
                st.rerun()
            elif "Add '" in selected_option and st.session_state.manual_selected_swimmer:
                st.session_state.manual_selected_swimmer = None
                st.rerun()

    manual_name = st.text_input("Swimmer Name*", value=prefilled_name)
    c1, c2, c3 = st.columns(3)
    gender_options = ["Male (ชาย)", "Female (หญิง)"]
    manual_gender = c1.selectbox("Gender*", gender_options, index=gender_options.index(prefilled_gender) if prefilled_gender in gender_options else 0)
    manual_club = c2.text_input("Club", value=prefilled_club)
    all_schools = [""] + sorted(db.get_schools()['ThaiSchool'].tolist())
    manual_school = c3.selectbox("School", all_schools, index=all_schools.index(prefilled_school) if prefilled_school in all_schools else 0)

    # --- 2. Competition Selection ---
    st.subheader("2. Find or Add Competition")
    competition_search_term = st.text_input("Search Competition", st.session_state.manual_competition_search, key='competition_search_input')
    if competition_search_term != st.session_state.manual_competition_search:
        st.session_state.manual_competition_search = competition_search_term
        st.session_state.manual_selected_competition = None
        st.rerun()

    prefilled_comp_name, prefilled_comp_date = st.session_state.manual_competition_search, date.today()
    if st.session_state.manual_selected_competition:
        prefilled_comp_name = st.session_state.manual_selected_competition
        date_str = db.get_competition_date(prefilled_comp_name)
        if date_str and (parsed_date := parse_thai_date(date_str)) is not None and not pd.isna(parsed_date):
            prefilled_comp_date = parsed_date.date()

    if st.session_state.manual_competition_search and (comp_results := db.search_competitions(st.session_state.manual_competition_search)):
        comp_options = [f"Use '{st.session_state.manual_competition_search}' as new competition"] + comp_results
        selected_comp = st.radio("Select a competition or confirm new:", comp_options, key="comp_select_radio")
        selected_comp_name = selected_comp.replace("Use '", "").replace("' as new competition", "")
        if st.session_state.manual_selected_competition != selected_comp_name:
            st.session_state.manual_selected_competition = selected_comp_name
            st.rerun()

    manual_competition = st.text_input("Competition Name*", value=prefilled_comp_name)
    manual_competition_date = st.date_input("Competition Date*", value=prefilled_comp_date)

    # --- 3. Event Details ---
    st.subheader("3. Enter Event Details")
    stroke_options = [s['name'] for s in SwimDataScraper.STROKES.values()]
    freestyle_index = stroke_options.index("FreeStyle (ฟรีสไตล์)") if "FreeStyle (ฟรีสไตล์)" in stroke_options else 0
    c_age, c_stroke = st.columns(2)
    manual_age = c_age.text_input("Age (e.g., 9 or 10-11)*")
    manual_stroke = c_stroke.selectbox("Stroke*", stroke_options, index=freestyle_index)
    c_dist, c_min, c_sec = st.columns(3)
    manual_distance = c_dist.selectbox("Distance*", [d['name'] for d in SwimDataScraper.DISTANCES.values()])
    manual_min = c_min.number_input("Time (Min)", min_value=0, step=1, format="%d")
    manual_sec = c_sec.number_input("Time (Sec)", min_value=0.0, max_value=59.99, step=0.01, format="%.2f")
    manual_nationality = st.text_input("Nationality", value="THA")

    # --- 4. Submit ---
    st.subheader("4. Save Record")
    if st.button("💾 Add Record"):
        manual_time = f"{manual_min:02d}:{manual_sec:05.2f}"
        if not manual_name.strip() or not manual_competition.strip() or not all([manual_age, manual_stroke, manual_distance, manual_time]):
            st.error("Please fill in all required fields (marked with *).")
        else:
            record_data = {
                "name": manual_name.strip(), "gender": manual_gender, "age": manual_age,
                "stroke": manual_stroke, "distance": manual_distance, "time": manual_time,
                "competition": manual_competition.strip(), "competition_date": format_date_to_thai_buddhist(manual_competition_date),
                "club": manual_club.strip(), "school": manual_school, "nationality": manual_nationality.strip()
            }
            if db.add_single_record(record_data):
                st.success(f"Record for {manual_name.strip()} added!")
                for key in st.session_state:
                    if key.startswith('manual_'): st.session_state[key] = "" if 'search' in key else None
                st.rerun()
            else:
                st.warning(f"Record for {manual_name.strip()} might already exist or an error occurred.")

def scraping_and_management_page():
    st.title("🏊 Data Management")
    st.header("🔍 Scrape New Rankings")
    scraper_choice = st.radio("Choose Scraper", ("Selenium", "AJAX"), key="scraper_choice")

    with st.expander("Show Scraper Options", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        stroke_k = c1.selectbox("Stroke", list(SwimDataScraper.STROKES.keys()), format_func=lambda x: SwimDataScraper.STROKES[x]['name'])
        dist_k = c2.selectbox("Distance", list(SwimDataScraper.DISTANCES.keys()), format_func=lambda x: SwimDataScraper.DISTANCES[x]['name'])
        gender_k = c3.selectbox("Gender", list(SwimDataScraper.GENDERS.keys()), format_func=lambda x: SwimDataScraper.GENDERS[x]['name'])
        pool_k = c4.selectbox("Pool", list(SwimDataScraper.POOL_TYPES.keys()), format_func=lambda x: SwimDataScraper.POOL_TYPES[x]['name'])
        c5, c6, c7 = st.columns([1, 1, 2])
        min_age = c5.number_input("Min Age", 5, 90, 10)
        max_age = c6.number_input("Max Age", 5, 90, 11)
        start_d, end_d = c7.date_input("Select Date Range", (date.today() - timedelta(days=365), date.today()))
        st.caption(f"Search window: **{start_d.strftime('%d %b %Y')}** to **{end_d.strftime('%d %b %Y')}**")

    if st.button("🚀 Fetch Rankings"):
        scraper = SwimDataScraper(headless=True) if scraper_choice == "Selenium" else SwimDataAjaxScraper()
        try:
            with st.status("Initializing Scraper...", expanded=True) as status:
                st.write(f"Applying filter: {start_d} to {end_d}")
                df = scraper.scrape_rankings(
                    SwimDataScraper.STROKES[stroke_k], SwimDataScraper.DISTANCES[dist_k],
                    SwimDataScraper.GENDERS[gender_k], SwimDataScraper.POOL_TYPES[pool_k],
                    str(min_age), str(max_age), start_d, end_d
                )
                st.session_state.scraped_data = df
                if df is not None:
                    status.update(label=f"Fetched {len(df)} records!", state="complete", expanded=False)
                    st.success(f"Successfully retrieved {len(df)} swimmers." if not df.empty else "The search returned no results.")
                else:
                    status.update(label="Scraping Failed", state="error")
                    st.error("An error occurred during scraping. Check logs for details.")
        finally:
            if 'scraper' in locals() and scraper: scraper.close()

    if 'scraped_data' in st.session_state and st.session_state.scraped_data is not None:
        df = st.session_state.scraped_data
        st.subheader("📊 Scraped Results")
        if not df.empty:
            st.dataframe(df, width='stretch')
            if st.button("💾 Save Results to Database"):
                with st.spinner("Saving..."):
                    added_count = db.add_records(df)
                    st.success(f"Successfully saved {added_count} new records.")
        else:
            st.info("Last search returned no data.")
    st.divider()

    st.header("✏️ Edit Records")
    st.info("Here you can directly edit saved records. UniqueID and Name cannot be edited.", icon="ℹ️")
    if 'record_editor_key' not in st.session_state: st.session_state.record_editor_key = 0
    edited_records_df = st.data_editor(db.get_records(), width='stretch', num_rows="dynamic", key=f"record_editor_{st.session_state.record_editor_key}", disabled=['UniqueID', 'SwimmerUniqID', 'Name'])
    if st.button("💾 Save Record Changes"):
        with st.spinner("Saving..."): updated_count = db.sync_records(edited_records_df)
        st.success(f"{updated_count} records have been updated!")
        st.session_state.record_editor_key += 1
        st.rerun()
    st.divider()

    st.header("🗑️ Delete Records")
    st.warning("This is a destructive action. Deleted records cannot be recovered.", icon="⚠️")
    
    all_records_for_deletion = db.get_records()
    if not all_records_for_deletion.empty:
        all_records_for_deletion['display_str'] = all_records_for_deletion.apply(
            lambda row: f"{row.get('Name', 'N/A')} - {row.get('Competition', 'N/A')} ({row.get('Stroke', 'N/A')}, {row.get('Distance', 'N/A')}) - {row.get('Time', 'N/A')}",
            axis=1
        )
        display_to_id_map = pd.Series(all_records_for_deletion.UniqueID.values, index=all_records_for_deletion.display_str).to_dict()
        
        records_to_delete_display = st.multiselect(
            "Select records to delete",
            options=all_records_for_deletion['display_str'].tolist()
        )
        
        if st.button("Delete Selected Records", type="primary"):
            if not records_to_delete_display:
                st.error("Please select at least one record to delete.")
            else:
                ids_to_delete = [display_to_id_map[display] for display in records_to_delete_display]
                with st.spinner("Deleting records..."):
                    deleted_count = db.delete_records(ids_to_delete)
                st.success(f"Successfully deleted {deleted_count} record(s).")
                st.rerun()
    else:
        st.info("No records in the database to delete.")

    st.divider()
    
    st.header("🏊‍♀️ Swimmer Management")
    st.info("Here you can edit swimmer details.", icon="ℹ️")
    if 'editor_key' not in st.session_state: st.session_state.editor_key = 0
    all_schools_for_editor = [""] + sorted(db.get_schools()['ThaiSchool'].tolist())
    edited_df = st.data_editor(
        db.get_swimmers(), width='stretch', num_rows="dynamic", key=f"swimmer_editor_{st.session_state.editor_key}",
        column_config={
            "UniqID": st.column_config.TextColumn("Unique ID", disabled=True),
            "YearOfBirth": st.column_config.NumberColumn("Birth Year", format="%d", step=1),
            "Gender": st.column_config.SelectboxColumn("Gender", options=["Male (ชาย)", "Female (หญิง)"], required=True),
            "School": st.column_config.SelectboxColumn("School", options=all_schools_for_editor),
        }
    )
    if st.button("💾 Save Swimmer Changes"):
        with st.spinner("Saving..."): db.sync_swimmers(edited_df)
        st.success("Swimmer profiles have been updated!")
        st.session_state.editor_key += 1
        st.rerun()
    st.divider()

    st.header("🏫 School Management")
    st.info("Here you can add, edit, or delete school details.", icon="ℹ️")
    if 'school_table_editor_key' not in st.session_state: st.session_state.school_table_editor_key = 0
    edited_schools_df = st.data_editor(
        db.get_schools(), width='stretch', num_rows="dynamic", key=f"school_table_editor_{st.session_state.school_table_editor_key}",
        column_config={
            "ThaiSchool": st.column_config.TextColumn("Thai School Name", required=True),
            "ThaiAbridgeName": st.column_config.TextColumn("Thai Abbr. Name"),
            "EngAbridge": st.column_config.TextColumn("Eng. Abbr. Name"),
            "SATITGAME": st.column_config.CheckboxColumn("SATITGAME Participant", default=False),
        }
    )
    if st.button("💾 Save School Changes", key="save_school_table_changes"):
        with st.spinner("Saving..."): db.sync_schools(edited_schools_df)
        st.success("School data updated!")
        st.session_state.school_table_editor_key += 1
        st.rerun()

def dashboard_page():
    st.header("📊 Ranking Dashboard")
    st.info("Explore and analyze your saved swimming records.")
    records_df = db.get_records()
    if records_df.empty:
        st.warning("No records found in the database. Scrape and save some data first!")
        return

    st.subheader("Filter Records")
    records_df['CompetitionDate'] = records_df['CompetitionDate'].apply(parse_thai_date)
    records_df[['_min_age_val', '_max_age_val']] = records_df['Age'].apply(lambda x: pd.Series(parse_age_range(x)))
    records_df.dropna(subset=['_min_age_val', '_max_age_val'], inplace=True)
    all_genders, all_strokes, all_distances = ["All"] + records_df['Gender'].dropna().unique().tolist(), ["All"] + records_df['Stroke'].dropna().unique().tolist(), ["All"] + records_df['Distance'].dropna().unique().tolist()
    all_schools, all_clubs = records_df['School'].dropna().unique().tolist(), sorted(records_df['Club'].dropna().unique().tolist())
    
    c1, c2, c3, c4, c5 = st.columns(5)
    selected_gender = c1.selectbox("Gender", all_genders)
    selected_filter_min_age = c2.number_input("Min Age", 0, 200, 0)
    selected_filter_max_age = c3.number_input("Max Age", 0, 200, 200)
    selected_stroke = c4.selectbox("Stroke", all_strokes)
    selected_distance = c5.selectbox("Distance", all_distances)
    c6, c7 = st.columns(2)
    selected_schools = c6.multiselect("School", all_schools)
    selected_clubs = c7.multiselect("Club", all_clubs)

    filtered_df = records_df.copy()
    if selected_gender != "All": filtered_df = filtered_df[filtered_df['Gender'] == selected_gender]
    if selected_stroke != "All": filtered_df = filtered_df[filtered_df['Stroke'] == selected_stroke]
    if selected_distance != "All": filtered_df = filtered_df[filtered_df['Distance'] == selected_distance]
    if selected_schools: filtered_df = filtered_df[filtered_df['School'].isin(selected_schools)]
    if selected_clubs: filtered_df = filtered_df[filtered_df['Club'].isin(selected_clubs)]
    filtered_df = filtered_df[filtered_df['_max_age_val'] >= selected_filter_min_age]
    filtered_df = filtered_df[filtered_df['_min_age_val'] <= selected_filter_max_age]
        
    if filtered_df.empty:
        st.warning("No records match the selected filters.")
        return

    st.subheader("Summary Statistics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", len(filtered_df))
    c2.metric("Unique Swimmers", filtered_df['Name'].nunique())
    c3.metric("Unique Competitions", filtered_df['Competition'].nunique())

    st.subheader("Records by Stroke")
    display_cols = ['Name', 'Distance', 'Time', 'CompetitionDate', 'Competition']
    strokes_to_display = {s['name']: f"{s['name'].split(' ')[0]} Records" for s in SwimDataScraper.STROKES.values()}
    for stroke_name, table_title in strokes_to_display.items():
        stroke_df = filtered_df[filtered_df['Stroke'] == stroke_name]
        if not stroke_df.empty:
            st.markdown(f"**{table_title}**")
            st.dataframe(stroke_df[display_cols], width='stretch')

def main():
    db.init_db()
    if 'scraped_data' not in st.session_state: st.session_state.scraped_data = None
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ("Dashboard", "Data Management", "Add Record"), index=0)

    if page == "Dashboard":
        st.title("📊 Ranking Dashboard")
        dashboard_page()
    elif page == "Data Management":
        scraping_and_management_page()
    elif page == "Add Record":
        add_record_page()

if __name__ == "__main__":
    main()
