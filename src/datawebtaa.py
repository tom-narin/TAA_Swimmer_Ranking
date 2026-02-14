import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import tempfile
import os
from datetime import datetime
from selenium.common.exceptions import TimeoutException

class SwimDataScraper:
    STROKES = {
        "1": {"name": "FreeStyle (ฟรีสไตล์)", "id": "2"},
        "2": {"name": "Backstroke (กรรเชียง)", "id": "3"},
        "3": {"name": "Breaststroke (กบ)", "id": "4"},
        "4": {"name": "Butterfly (ผีเสื้อ)", "id": "5"},
        "5": {"name": "Individual Medley (เดี่ยวผสม)", "id": "6"}
    }
    DISTANCES = {
        "1": {"name": "50 m", "id": "1"},
        "2": {"name": "100 m", "id": "2"},
        "3": {"name": "200 m", "id": "3"},
        "4": {"name": "400 m", "id": "4"},
        "5": {"name": "800 m", "id": "5"},
        "6": {"name": "1500 m", "id": "9"}
    }
    GENDERS = {
        "1": {"name": "Male (ชาย)", "id": "1"},
        "2": {"name": "Female (หญิง)", "id": "2"}
    }
    POOL_TYPES = {
        "1": {"name": "Long Course (50m)", "id": "1"},
        "2": {"name": "Short Course (25m)", "id": "2"}
    }

    def __init__(self, headless=True):
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument('--headless=new')
            self.options.add_argument("--no-sandbox")
            self.options.add_argument("--disable-gpu")
            self.options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 15)
        self.initial_url = "https://www.thaiaquatics.or.th/Index/HomeRanking?Distance=1&SwimmingTypeDetailId=2"

    def _select_and_wait(self, element_id, value):
        select_element = self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
        dropdown = Select(select_element)
        dropdown.select_by_value(value)
        print(f"[DEBUG] Selection: ID={element_id} set to '{dropdown.first_selected_option.text}'")
        try:
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
        except: pass

    def _enter_text_and_wait(self, element_id, text):
        # We use a more robust JS script to ensure value is set and events are triggered
        script = f"""
            var el = document.getElementById('{element_id}');
            el.value = '{text}';
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            el.blur();
        """
        self.driver.execute_script(script)
        # Verify
        actual_val = self.driver.execute_script(f"return document.getElementById('{element_id}').value;")
        print(f"[DEBUG] Input: ID={element_id} | Target='{text}' | Actual='{actual_val}'")
        try:
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
        except: pass

    def scrape_rankings(self, stroke, dist, gender, pool, min_age, max_age, start_date, end_date):
        try:
            print(f"[DEBUG] Starting scrape: {start_date} to {end_date}")
            self.driver.get(self.initial_url)
            self.wait.until(EC.presence_of_element_located((By.ID, 'SwimmingTypeDetail')))
            
            # Format dates as DD/MM/YYYY (Standard for Thai web input)
            start_str = start_date.strftime('%d/%m/%Y')
            end_str = end_date.strftime('%d/%m/%Y')

            self._select_and_wait('SwimmingTypeDetail', stroke['id'])
            self._select_and_wait('Distance', dist['id'])
            self._select_and_wait('GenderGroup', gender['id'])
            self._select_and_wait('PoolLengthId', pool['id'])
            
            self._enter_text_and_wait('AgeGroupMin', min_age)
            self._enter_text_and_wait('AgeGroupMax', max_age)
            
            # Input Dates
            self._enter_text_and_wait('StartDate', start_str)
            self._enter_text_and_wait('EndDate', end_str)
            
            # Wait for any background updates
            time.sleep(2)
            
            table_element = self.wait.until(EC.presence_of_element_located((By.ID, 'ResultTable')))
            html = table_element.get_attribute('outerHTML')
            dfs = pd.read_html(html, flavor='html5lib')
            
            if not dfs or dfs[0].empty:
                print("[DEBUG] No table data found in HTML")
                return pd.DataFrame()
            
            df = dfs[0]
            if 'No data' in str(df.iloc[0,0]):
                print("[DEBUG] Table contains 'No data available'")
                return pd.DataFrame()

            # Clean columns - expected columns: Rank, Name, Club, Nationality, Time, Competition, Start, End
            if len(df.columns) >= 8:
                df.columns = ['Rank', 'Name', 'Club', 'Nationality', 'Time', 'Competition', 'StartDate', 'EndDate']
            
            print(f"[DEBUG] Successfully scraped {len(df)} rows.")
            return df
            
        except Exception as e:
            print(f"[DEBUG] ERROR during scrape: {str(e)}")
            return None

    def close(self):
        if self.driver: self.driver.quit()
