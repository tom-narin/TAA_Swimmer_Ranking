import unittest
import os
import sys
import pandas as pd

# Add the parent directory of the current file to sys.path
# This allows importing 'datawebtaa' as a module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from datawebtaa import SwimDataScraper 
class TestSwimDataScraper(unittest.TestCase):

    # Define test cases mapping to the internal structure of SwimDataScraper
    # Note: The keys here are the user input choice numbers, not the internal IDs
    TEST_CASES = [
        # Stroke, Distance, Gender, Pool, MinAge, MaxAge
        ("1", "1", "2", "1", "9", "9"), # FreeStyle 50m LC Girl 9-9
        ("1", "2", "2", "1", "9", "9"), # FreeStyle 100m LC Girl 9-9
        ("1", "3", "2", "1", "9", "9"), # FreeStyle 200m LC Girl 9-9
        ("4", "1", "2", "1", "9", "9"), # Butterfly 50m LC Girl 9-9
        ("2", "1", "2", "1", "9", "9"), # Backstroke 50m LC Girl 9-9
        ("3", "1", "2", "1", "9", "9"), # Breaststroke 50m LC Girl 9-9
        ("5", "3", "2", "1", "9", "9"), # Individual Medley 200m LC Girl 9-9
    ]

    def test_scrape_rankings_with_predefined_inputs(self):
        # Create a dummy scraper instance to access mappings.
        # This one doesn't need to launch a browser, as it's only for accessing STROKES etc.
        dummy_scraper = SwimDataScraper(headless=True) 
        
        for i, (stroke_choice, dist_choice, gender_choice, pool_choice, min_age, max_age) in enumerate(self.TEST_CASES):
            with self.subTest(f"Test Case {i+1}: Stroke={stroke_choice}, Dist={dist_choice}, Gender={gender_choice}, Pool={pool_choice}, Age={min_age}-{max_age}"):
                scraper = SwimDataScraper(headless=True) # Run each test in headless mode
                expected_filename = "" # Initialize here for outer finally block
                try:
                    # Retrieve the full info dictionaries based on user input choices
                    sel_stroke_info = scraper.STROKES.get(stroke_choice)
                    sel_dist_info = scraper.DISTANCES.get(dist_choice)
                    sel_gender_info = scraper.GENDERS.get(gender_choice)
                    sel_pool_info = scraper.POOL_TYPES.get(pool_choice)

                    self.assertIsNotNone(sel_stroke_info, f"Invalid stroke choice: {stroke_choice}")
                    self.assertIsNotNone(sel_dist_info, f"Invalid distance choice: {dist_choice}")
                    self.assertIsNotNone(sel_gender_info, f"Invalid gender choice: {gender_choice}")
                    self.assertIsNotNone(sel_pool_info, f"Invalid pool type choice: {pool_choice}")

                    # Generate expected filename to check for existence
                    expected_filename = f"TAA_Ranking_Age{min_age}-{max_age}_{sel_gender_info['name']}_{sel_stroke_info['name']}_{sel_dist_info['name']}_{sel_pool_info['name']}.csv"
                    expected_filename = expected_filename.replace(" ", "_").replace("(", "").replace(")", "")
                    
                    # Ensure file does not exist from previous runs
                    if os.path.exists(expected_filename):
                        os.remove(expected_filename)

                    df = scraper.scrape_rankings(
                        sel_stroke_info, 
                        sel_dist_info, 
                        sel_gender_info, 
                        sel_pool_info, 
                        min_age, 
                        max_age
                    )
                    
                    self.assertIsNotNone(df, "scrape_rankings returned None (indicating an error)")
                    self.assertIsInstance(df, pd.DataFrame, "scrape_rankings did not return a DataFrame")
                    # Check if the DataFrame has some columns (assuming a successful scrape would have columns)
                    self.assertGreater(len(df.columns), 0, "DataFrame has no columns, indicating potential parsing issue or no data.")
                    # Check if the CSV file was created
                    self.assertTrue(os.path.exists(expected_filename), f"CSV file was not created: {expected_filename}")
                    # Optionally, check if the CSV file has content (e.g., more than just headers)
                    self.assertGreater(os.path.getsize(expected_filename), 100, f"CSV file '{expected_filename}' is too small or empty.")

                finally:
                    scraper.close()
                    # Clean up the created CSV file
                   # if os.path.exists(expected_filename):
                   #     #os.remove(expected_filename)
        dummy_scraper.close() # Close dummy scraper, as it launched a headless browser.

if __name__ == '__main__':
    unittest.main()
