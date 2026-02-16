import pandas as pd
import requests
import json
from datetime import datetime

class SwimDataAjaxScraper:
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

    def __init__(self, headless=True): # headless parameter is ignored for AJAX scraper
        self.base_url = "https://www.thaiaquatics.or.th"
        self.session = requests.Session()
        # Optionally perform an initial GET request to get session cookies and any CSRF token
        # response = self.session.get(self.base_url + "/Index/HomeRanking")
        # response.raise_for_status()

    def scrape_rankings(self, stroke, dist, gender, pool, min_age, max_age, start_date, end_date):
        try:
            # Format dates as DD/Mon/YY (2-digit Gregorian year), matching the website's JS
            start_str = start_date.strftime('%d/%b/%y')
            end_str = end_date.strftime('%d/%b/%y')

            # Construct ModelCompetition object as in JS
            model_competition = {
                "TimestdF": "", # Not available from Streamlit UI, assume empty
                "SwimmingTypeDetailId": stroke['id'],
                "GenderId": gender['id'],
                "DistId": dist['id'],
                "AgeMax": max_age,
                "AgeMin": min_age,
                "PoolLengthId": pool['id'],
                "NationId": "0" # Not available from Streamlit UI, assume 0 for "All"
            }

            # Construct dataAjax object as in JS
            data_ajax = {
                "CompetitionEvent": json.dumps(model_competition), # json.dumps to match JS JSON.stringify
                "startDate": start_str,
                "endDate": end_str,
                # Add minimal DataTables server-side processing parameters
                "draw": 1,
                "start": 0,
                "length": -1, # -1 tells DataTables to return all records
                "search[value]": "",
                "search[regex]": "false"
            }

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest', # Mimic AJAX request
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # URL for the AJAX call
            ajax_url = self.base_url + "/Index/CheckRank"

            print(f"[DEBUG] Sending AJAX request to {ajax_url} with data: {data_ajax}")
            response = self.session.post(ajax_url, data=data_ajax, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors

            json_data = response.json()

            if 'data' in json_data and json_data['data']:
                records = []
                for item in json_data['data']:
                    record = {
                        'Rank': item.get('Place'),
                        'Name': item.get('FullName'),
                        'Club': item.get('ClubName'),
                        'Nationality': item.get('Nation'),
                        'Time': item.get('Time'),
                        'Competition': item.get('Competition', {}).get('Name'),
                        'CompetitionDate': item.get('Competition', {}).get('StartDayString'),
                    }
                    records.append(record)
                
                df = pd.DataFrame(records)
                
                # Add context columns from scrape parameters (still needed as they are not in the raw AJAX response)
                df['Stroke'] = stroke['name']
                df['Distance'] = dist['name']
                df['AgeRange'] = f"{min_age}-{max_age}"
                df['Pool'] = pool['name']
                df['Gender'] = gender['name']

                print(f"[DEBUG] AJAX fetched {len(df)} records.")
                return df
            else:
                print("[DEBUG] AJAX response contains no 'data' or is empty.")
                return pd.DataFrame()

        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] ERROR during AJAX scrape: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[DEBUG] ERROR decoding JSON response: {e}")
            # print(f"Response content: {response.text[:500]}...")
            return None
        except Exception as e:
            print(f"[DEBUG] General ERROR during AJAX scrape: {e}")
            return None

    def close(self):
        self.session.close()
