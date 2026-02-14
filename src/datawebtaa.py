import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import tempfile
import os

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
        self.options = webdriver.ChromeOptions()
        if headless:
            self.options.add_argument("--headless")
            self.options.add_argument("--no-sandbox")
            self.options.add_argument("--disable-dev-shm-usage")
            self.options.add_argument("--disable-gpu")
            self.options.add_argument("--window-size=1920x1080")
            self.options.add_argument("--disable-extensions")

        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.wait = WebDriverWait(self.driver, 10)
        self.initial_url = "https://www.thaiaquatics.or.th/Index/HomeRanking?Distance=1&SwimmingTypeDetailId=2"

    def _select_and_wait(self, element_id, value):
        """Selects an option and waits for the table to reload if it does."""
        select_element = self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
        Select(select_element).select_by_value(value)
        try:
            # Wait for the "processing" overlay to appear, with a short timeout
            short_wait = WebDriverWait(self.driver, 2)
            short_wait.until(EC.visibility_of_element_located((By.ID, 'ResultTable_processing')))
            # If it appears, wait for it to disappear (with the original longer wait)
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
            print(f"Selected '{value}' in {element_id}, data reloaded.")
        except TimeoutException:
            # If the overlay doesn't appear, just log it and continue
            print(f"Selected '{value}' in {element_id}, no data reload detected.")

    def _enter_text_and_wait(self, element_id, text):
        """Enters text into an input field using JavaScript and waits for the table to reload if it does."""
        # Use JavaScript to set the value, which often bypasses interactability issues.
        script = f"document.getElementById('{element_id}').value = '{text}';"
        self.driver.execute_script(script)
        # After setting the value, it's good practice to trigger a change event
        # or move focus to simulate user interaction and trigger website's JS logic.
        self.driver.execute_script(f"document.getElementById('{element_id}').dispatchEvent(new Event('change'));")
        self.driver.execute_script(f"document.getElementById('{element_id}').blur();") # Simulate losing focus

        try:
            # Wait for the "processing" overlay to appear, with a short timeout
            short_wait = WebDriverWait(self.driver, 2)
            short_wait.until(EC.visibility_of_element_located((By.ID, 'ResultTable_processing')))
            # If it appears, wait for it to disappear (with the original longer wait)
            self.wait.until(EC.invisibility_of_element_located((By.ID, 'ResultTable_processing')))
            print(f"Entered '{text}' in {element_id} via JS, data reloaded.")
        except TimeoutException:
            # If the overlay doesn't appear, just log it and continue
            print(f"Entered '{text}' in {element_id} via JS, no data reload detected.")

    def _get_selection_from_user(self):
        print("\n--- Select Stroke ---")
        for k, v in self.STROKES.items(): print(f"{k}. {v['name']}")
        s_choice = input(f"Enter number (1-{len(self.STROKES)}): ")

        print("\n--- Select Distance ---")
        for k, v in self.DISTANCES.items(): print(f"{k}. {v['name']}")
        d_choice = input(f"Enter number (1-{len(self.DISTANCES)}): ")

        print("\n--- Select Gender ---")
        for k, v in self.GENDERS.items(): print(f"{k}. {v['name']}")
        g_choice = input(f"Enter number (1-{len(self.GENDERS)}): ")

        print("\n--- Select Pool Type ---")
        for k, v in self.POOL_TYPES.items(): print(f"{k}. {v['name']}")
        p_choice = input(f"Enter number (1-{len(self.POOL_TYPES)}): ")
        
        print("\n--- Enter Age Range ---")
        min_age_choice = input("Enter minimum age (e.g., 9): ")
        max_age_choice = input("Enter maximum age (e.g., 10): ")

        return (
            self.STROKES.get(s_choice), 
            self.DISTANCES.get(d_choice),
            self.GENDERS.get(g_choice),
            self.POOL_TYPES.get(p_choice),
            min_age_choice,
            max_age_choice
        )

    def scrape_rankings(self, sel_stroke_info, sel_dist_info, sel_gender_info, sel_pool_info, min_age, max_age):
        try:
            self.driver.get(self.initial_url)
            self.wait.until(EC.presence_of_element_located((By.ID, 'SwimmingTypeDetail')))

            # Use the passed dictionary info directly
            stroke_name = sel_stroke_info['name']
            dist_name = sel_dist_info['name']
            gender_name = sel_gender_info['name']
            pool_type_name = sel_pool_info['name']

            print(f"\nLaunching browser to search: {stroke_name} {dist_name} (Age {min_age}-{max_age}, {gender_name}, {pool_type_name})...")


            # Make selections for the user's choice
            # We don't need to re-select the defaults (Dist=1, Stroke=2) if they match the user's choice
            # Default stroke id is "2" for FreeStyle. Default dist id is "1" for 50m.
            if sel_stroke_info['id'] != "2": 
                self._select_and_wait('SwimmingTypeDetail', sel_stroke_info['id'])
            
            if sel_dist_info['id'] != "1":
                self._select_and_wait('Distance', sel_dist_info['id'])
                
            time.sleep(2) # Introduce a small delay for debugging potential timing issues
            self._enter_text_and_wait('AgeGroupMin', min_age)
            self._enter_text_and_wait('AgeGroupMax', max_age)
            self._select_and_wait('GenderGroup', sel_gender_info['id'])
            self._select_and_wait('PoolLengthId', sel_pool_info['id'])
            
            print("All selections made. Final data loaded.")

            # Get the table HTML
            table_element = self.driver.find_element(By.ID, 'ResultTable')
            table_html = table_element.get_attribute('outerHTML')
            
            temp_file_path = None # Initialize outside try for finally access
           
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html', encoding='utf-8') as temp_file:
                    temp_file.write(table_html)
                    temp_file_path = temp_file.name
            
                
                df = pd.read_html(temp_file_path, flavor='html5lib')[0]
                print (df)
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            if not df.empty:
                # Drop the last row if it's the "No data available in table" message
                if 'No data available in table' in df.iloc[-1].to_string():
                    df = df.iloc[:-1]

            if not df.empty:
                print("\nTop Rankings Found:")
                # Rename columns for clarity. Note: The columns are based on the table's visual output.
                df.columns = ['Rank', 'Name', 'Club', 'Nationality', 'Time', 'Competition', 'StartDate', 'EndDate']
                print(df.head(5))
                
                # Save file
                filename = f"TAA_Ranking_Age{min_age}-{max_age}_{gender_name}_{stroke_name}_{dist_name}_{pool_type_name}.csv"
                filename = filename.replace(" ", "_").replace("(", "").replace(")", "")
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                print(f"\nSaved successfully to: {filename}")
                return df # Return dataframe for testing purposes
            else:
                print("No ranking data found for this criteria.")
                return pd.DataFrame() # Return empty DataFrame
                
        except Exception as e:
            print(f"An error occurred: {e}")
            return None # Indicate failure

    def close(self):
        if self.driver:
            self.driver.quit()
            print("\nBrowser closed.")

# Main execution for interactive use
if __name__ == '__main__':
    scraper = SwimDataScraper(headless=False) # Keep browser visible for interactive use
    try:
        sel_stroke_info, sel_dist_info, sel_gender_info, sel_pool_info, sel_min_age, sel_max_age = scraper._get_selection_from_user()

        if all([sel_stroke_info, sel_dist_info, sel_gender_info, sel_pool_info, sel_min_age, sel_max_age]):
            scraper.scrape_rankings(
                sel_stroke_info, 
                sel_dist_info, 
                sel_gender_info, 
                sel_pool_info, 
                sel_min_age, 
                sel_max_age
            )
        else:
            print("Invalid Selection. Please try again.")
    finally:
        scraper.close()
