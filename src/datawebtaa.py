import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import tempfile
import os
from datetime import datetime

from selenium.common.exceptions import TimeoutException

class SwimDataScraper:
    # Mappings based on website's HTML and JavaScript
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
        # Configuration for Streamlit Cloud and Local
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument('--headless=new')
            self.options.add_argument("--no-sandbox")
            self.options.add_argument("--disable-gpu")
            self.options.add_argument("--disable-dev-shm-usage")
            self.options.add_argument("--window-size=1920x1080")
        
        # Selenium 4.10+ automatically finds driver if installed via packages.txt
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 15)
        self.initial_url = "https://www.thaiaquatics.or.th/Index/HomeRanking?Distance=1&SwimmingTypeDetailId=2"

    def _select_and_wait(self, element_id, value):
        select_element = self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
        Select(select_element).select_by_value(value)
        try:
            short_wait = WebDriverWait(self.driver, 2)
            short_wait.until(EC.visibility_of_element_located((By.ID, 'ResultTable_processing')))
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
        except TimeoutException:
            pass

    def _enter_text_and_wait(self, element_id, text):
        script = f"document.getElementById('{element_id}').value = '{text}';"
        self.driver.execute_script(script)
        self.driver.execute_script(f"document.getElementById('{element_id}').dispatchEvent(new Event('change'));")
        self.driver.execute_script(f"document.getElementById('{element_id}').blur();")
        try:
            short_wait = WebDriverWait(self.driver, 2)
            short_wait.until(EC.visibility_of_element_located((By.ID, 'ResultTable_processing')))
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
        except TimeoutException:
            pass

    def scrape_rankings(self, sel_stroke_info, sel_dist_info, sel_gender_info, sel_pool_info, min_age, max_age, start_date, end_date):
        try:
            self.driver.get(self.initial_url)
            self.wait.until(EC.presence_of_element_located((By.ID, 'SwimmingTypeDetail')))

            # Format dates to DD/MM/YYYY for the website's database
            start_str = start_date.strftime('%dd/%mm/%YY')
            end_str = end_date.strftime('%dd/%mm/%YY')
            print(start_str)
            print(end_str)

            # Make selections
            if sel_stroke_info['id'] != "2": 
                self._select_and_wait('SwimmingTypeDetail', sel_stroke_info['id'])
            
            if sel_dist_info['id'] != "1":
                self._select_and_wait('Distance', sel_dist_info['id'])
                
            self._enter_text_and_wait('AgeGroupMin', min_age)
            self._enter_text_and_wait('AgeGroupMax', max_age)
            self._select_and_wait('GenderGroup', sel_gender_info['id'])
            self._select_and_wait('PoolLengthId', sel_pool_info['id'])
            
            # Input the Dates
            self._enter_text_and_wait('StartDate', start_str)
            self._enter_text_and_wait('EndDate', end_str)
            
            # Final data fetch
            time.sleep(1)
            table_element = self.wait.until(EC.presence_of_element_located((By.ID, 'ResultTable')))
            table_html = table_element.get_attribute('outerHTML')
            
            temp_file_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html', encoding='utf-8') as temp_file:
                    temp_file.write(table_html)
                    temp_file_path = temp_file.name
                df = pd.read_html(temp_file_path, flavor='html5lib')[0]
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            if not df.empty:
                if 'No data available in table' in df.iloc[-1].to_string():
                    df = df.iloc[:-1]

            if not df.empty:
                df.columns = ['Rank', 'Name', 'Club', 'Nationality', 'Time', 'Competition', 'StartDate', 'EndDate']
                return df
            return pd.DataFrame()
                
        except Exception as e:
            print(f"Error: {e}")
            return None

    def close(self):
        if self.driver:
            self.driver.quit()
