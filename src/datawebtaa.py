import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import io
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
        # The TAA website often uses 'datepicker' libraries that override direct .value assignments.
        # We clear the field, type specifically, or use JS to force the internal library to update.
        script = f"""
            var el = document.getElementById('{element_id}');
            el.value = ''; 
            el.value = '{text}';
            // Force the 'change' event to propagate to jQuery/DatePicker listeners
            if (typeof(jQuery) !== 'undefined') {{
                jQuery(el).trigger('change');
            }} else {{
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
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
            
            # Format dates as DD/MMM/YY (matching website's datepicker format)
            start_str = start_date.strftime('%d/%b/%y')
            end_str = end_date.strftime('%d/%b/%y')

            # Standard selections
            self._select_and_wait('SwimmingTypeDetail', stroke['id'])
            self._select_and_wait('Distance', dist['id'])
            self._select_and_wait('GenderGroup', gender['id'])
            self._select_and_wait('PoolLengthId', pool['id'])
            self._enter_text_and_wait('AgeGroupMin', min_age)
            self._enter_text_and_wait('AgeGroupMax', max_age)
            
            # CRITICAL: Input dates AFTER other selections to prevent them from being reset
            self._enter_text_and_wait('StartDate', start_str)
            self._enter_text_and_wait('EndDate', end_str)

            try:
                # Attempt 1: Standard <select> element (keeping as a quick check)
                select_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#ResultTable_length select')))
                dropdown = Select(select_element)
                dropdown.select_by_value('-1')
                print("[DEBUG] Success: Used standard <select> to show all entries.")
                self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
            except TimeoutException:
                print("[DEBUG] Info: Standard <select> not found. Trying custom dropdown interaction (e.g., Bootstrap/DataTables style).")
                try:
                    # Attempt 2: Click a dropdown-toggle button, then find the 'All' link.
                    
                    # 1. Find and click the button that opens the dropdown menu.
                    # This targets a button with class 'dropdown-toggle' inside the length container.
                    trigger_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#ResultTable_length .dropdown-toggle')))
                    trigger_button.click()
                    print("[DEBUG] Info: Clicked dropdown trigger button.")

                    # 2. Wait for the 'All' option link to appear in the menu and click it.
                    all_option_link = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//ul[contains(@class, 'dropdown-menu')]//a[normalize-space()='All']")))
                    all_option_link.click()
                    
                    print("[DEBUG] Success: Used custom dropdown to show all entries.")
                    self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
                except Exception as e:
                    print(f"[DEBUG] Error: Failed to interact with custom dropdown. Proceeding with default. Error: {e}")
            
            time.sleep(2) # Final breather for JS updates
            
            table_element = self.wait.until(EC.presence_of_element_located((By.ID, 'ResultTable')))
            html = table_element.get_attribute('outerHTML')
            
            # Fix FutureWarning: wrap in StringIO
            dfs = pd.read_html(io.StringIO(html), flavor='html5lib')
            
            if not dfs or dfs[0].empty:
                return pd.DataFrame()
            
            df = dfs[0]
            if 'No data' in str(df.iloc[0,0]):
                print("[DEBUG] Table contains 'No data available'")
                return pd.DataFrame()

            if len(df.columns) >= 8:
                df.columns = ['Rank', 'Name', 'Club', 'Nationality', 'Time', 'Competition', 'StartDate', 'EndDate']
            
            # Add context columns from scrape parameters
            df['Stroke'] = stroke['name']
            df['Distance'] = dist['name']
            df['AgeRange'] = f"{min_age}-{max_age}" # Storing age as a range string
            df['Pool'] = pool['name']
            df['Gender'] = gender['name']

            # Rename StartDate to CompetitionDate and drop EndDate
            if 'StartDate' in df.columns:
                df.rename(columns={'StartDate': 'CompetitionDate'}, inplace=True)
            if 'EndDate' in df.columns:
                df.drop(columns=['EndDate'], inplace=True)
            
            print(f"[DEBUG] Successfully scraped {len(df)} rows.")
            return df
            
        except Exception as e:
            print(f"[DEBUG] ERROR during scrape: {str(e)}")
            return None

    def close(self):
        if self.driver: self.driver.quit()
