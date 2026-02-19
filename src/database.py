import sqlite3
import pandas as pd
import hashlib
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "swim_data.db")

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()

    # Swimmer Table - for unique swimmer profiles
    c.execute('''
        CREATE TABLE IF NOT EXISTS SwimmerTable (
            UniqID TEXT PRIMARY KEY,
            Name TEXT,
            Gender TEXT,
            YearOfBirth INTEGER,
            Club TEXT,
            School TEXT
        )
    ''')

    # Record Table - for individual race results
    c.execute('''
        CREATE TABLE IF NOT EXISTS RecordTable (
            UniqueID TEXT PRIMARY KEY,
            SwimmerUniqID TEXT,
            Name TEXT,
            Age TEXT,
            Stroke TEXT,
            Distance TEXT,
            Time TEXT,
            Competition TEXT,
            CompetitionDate TEXT,
            Club TEXT,
            Nationality TEXT,
            FOREIGN KEY (SwimmerUniqID) REFERENCES SwimmerTable (UniqID)
        )
    ''')

    # School Table - for pre-defined school names
    c.execute('''
        CREATE TABLE IF NOT EXISTS SchoolTable (
            ThaiSchool TEXT PRIMARY KEY,
            ThaiAbridgeName TEXT,
            EngAbridge TEXT,
            SATITGAME TEXT
        )
    ''')

    conn.commit()

    # Always refresh SchoolTable with latest data from file
    refresh_school_data('schoolname.txt') 

    conn.close()
    print("[DEBUG] Database initialized.")

def refresh_school_data(file_path='schoolname.txt'):
    """
    Clears the SchoolTable and then re-populates it from the specified file.
    This ensures the SchoolTable is always up-to-date with the schoolname.txt file.
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM SchoolTable")
    conn.commit()
    conn.close()
    abs_file_path = os.path.join(os.path.dirname(__file__), file_path)
    print(f"[DEBUG] Refreshing SchoolTable from: {abs_file_path}")
    populate_school_table(abs_file_path)
    print("[DEBUG] SchoolTable refreshed.")

def populate_school_table(file_path):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()

    # Check if table is empty
    c.execute("SELECT COUNT(*) FROM SchoolTable")
    count_before = c.fetchone()[0]

    if count_before == 0:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Skip header line (assuming first line is header 'Item ThaiSchool ...')
                lines = f.readlines()[1:] 
                for line in lines:
                    parts = line.strip().split(maxsplit=4) # Split into max 5 parts
                    if len(parts) >= 5: # Ensure we have enough parts
                        # Item, ThaiSchool, ThaiAbridgeName, ENG.Abridge, SATITGAME
                        # Skip 'Item' part, use others
                        thai_school = parts[1]
                        thai_abridge_name = parts[2]
                        eng_abridge = parts[3]
                        satitgame = parts[4] if len(parts) > 4 else "" # Handle cases where SATITGAME might be missing
                        satitgame_str = "True" if satitgame.strip().upper() == "YES" else "False"

                        c.execute('''
                            INSERT OR IGNORE INTO SchoolTable (ThaiSchool, ThaiAbridgeName, EngAbridge, SATITGAME)
                            VALUES (?, ?, ?, ?)
                        ''', (thai_school, thai_abridge_name, eng_abridge, satitgame_str))
                conn.commit()
        except FileNotFoundError:
            print(f"[ERROR] SchoolName.txt not found at {file_path}. SchoolTable not populated.")
        except Exception as e:
            print(f"[ERROR] Error populating SchoolTable: {e}")
    conn.close()

def get_schools() -> pd.DataFrame:
    """Fetches all school data from the SchoolTable."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM SchoolTable", conn)
    conn.close()
    return df

def add_records(df: pd.DataFrame):
    """
    Adds scraped ranking data to the database.
    It populates both SwimmerTable and RecordTable.
    """
    if df.empty:
        return 0
        
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    records_added = 0

    for _, row in df.iterrows():
        swimmer_name = row['Name']
        if not isinstance(swimmer_name, str):
            continue
            
        swimmer_uniq_id = swimmer_name.replace(' ', '_').lower()

        # Add swimmer to SwimmerTable if not exists, including Gender
        c.execute('''
            INSERT OR IGNORE INTO SwimmerTable (UniqID, Name, Gender, Club)
            VALUES (?, ?, ?, ?)
        ''', (swimmer_uniq_id, swimmer_name, row.get('Gender'), row['Club']))

        # Create a unique ID for the record to prevent duplicates
        record_uid_str = f"{swimmer_uniq_id}{row.get('Competition', '')}{row.get('CompetitionDate', '')}{row.get('Stroke', '')}{row.get('Distance', '')}{row.get('Time', '')}"
        record_unique_id = hashlib.sha1(record_uid_str.encode()).hexdigest()

        # Add record to RecordTable
        try:
            age_to_record = row.get('AgeRange')
            if isinstance(age_to_record, str) and '-' in age_to_record:
                parts = age_to_record.split('-')
                if len(parts) == 2 and parts[0] == parts[1]:
                    age_to_record = parts[0]

            c.execute('''
                INSERT INTO RecordTable (UniqueID, SwimmerUniqID, Name, Age, Stroke, Distance, Time, Competition, CompetitionDate, Club, Nationality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record_unique_id,
                swimmer_uniq_id,
                swimmer_name,
                age_to_record,
                row.get('Stroke'),
                row.get('Distance'),
                row.get('Time'),
                row.get('Competition'),
                row.get('CompetitionDate'),
                row.get('Club'),
                row.get('Nationality')
            ))
            records_added += 1
        except sqlite3.IntegrityError:
            # This record already exists, skip.
            pass

    conn.commit()
    conn.close()
    print(f"[DEBUG] Added {records_added} new records to the database.")
    return records_added

def get_swimmers() -> pd.DataFrame:
    """Fetches all swimmer profiles from the database."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM SwimmerTable", conn)
    conn.close()
    return df

def sync_swimmers(df: pd.DataFrame):
    """
    Synchronizes the SwimmerTable with the provided DataFrame.
    Handles additions, updates, and deletions.
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()

    # Generate UniqID for new rows if they are empty (based on Name)
    df['UniqID'] = df.apply(
        lambda row: row['Name'].replace(' ', '_').lower() if pd.isna(row.get('UniqID')) and isinstance(row.get('Name'), str) else row.get('UniqID'),
        axis=1
    )
    df.dropna(subset=['UniqID'], inplace=True)
    df.drop_duplicates(subset=['UniqID'], keep='first', inplace=True)

    all_ids_in_df = tuple(df['UniqID'].unique())
    
    # Delete swimmers from DB that are not in the DataFrame anymore
    if all_ids_in_df:
        c.execute(f"DELETE FROM SwimmerTable WHERE UniqID NOT IN ({','.join('?' for _ in all_ids_in_df)})", all_ids_in_df)
    else:
        c.execute("DELETE FROM SwimmerTable")

    # Insert or Replace swimmers in the DB from the DataFrame
    for _, row in df.iterrows():
        # Ensure YearOfBirth is an integer or None
        yob = row.get('YearOfBirth')
        if yob is not None and not pd.isna(yob):
            try:
                yob = int(yob)
            except (ValueError, TypeError):
                yob = None
        else:
            yob = None

        c.execute('''
            INSERT OR REPLACE INTO SwimmerTable (UniqID, Name, Gender, YearOfBirth, Club, School)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (row['UniqID'], row['Name'], row.get('Gender'), yob, row['Club'], row['School']))
        
    conn.commit()
    conn.close()
    print(f"[DEBUG] Synced {len(df)} swimmers with the database.")

def get_records() -> pd.DataFrame:
    """Fetches all records from the database, including swimmer gender and school."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    query = """
    SELECT
        R.*,
        S.Gender,
        S.School
    FROM
        RecordTable AS R
    LEFT JOIN
        SwimmerTable AS S
    ON
        R.SwimmerUniqID = S.UniqID
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def add_single_record(data: dict) -> bool:
    """
    Adds a single record to the database manually.
    Ensures swimmer exists in SwimmerTable and then adds the record to RecordTable.
    Returns True on success, False on failure (e.g., duplicate record).
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()

    try:
        swimmer_name = data['name']
        swimmer_uniq_id = swimmer_name.replace(' ', '_').lower()

        # Ensure swimmer exists in SwimmerTable
        c.execute('''
            INSERT OR IGNORE INTO SwimmerTable (UniqID, Name, Gender, Club, School)
            VALUES (?, ?, ?, ?, ?)
        ''', (swimmer_uniq_id, swimmer_name, data.get('gender'), data.get('club'), data.get('school')))
        
        # Format age to record (handle "X-X" -> "X" logic)
        age_to_record = data.get('age')
        if isinstance(age_to_record, str) and '-' in age_to_record:
            parts = age_to_record.split('-')
            if len(parts) == 2 and parts[0] == parts[1]:
                age_to_record = parts[0]

        # Create a unique ID for the record
        record_uid_str = f"{swimmer_uniq_id}{data['competition']}{data['competition_date']}{data['stroke']}{data['distance']}{data['time']}"
        record_unique_id = hashlib.sha1(record_uid_str.encode()).hexdigest()

        # Add record to RecordTable
        c.execute('''
            INSERT INTO RecordTable (UniqueID, SwimmerUniqID, Name, Age, Stroke, Distance, Time, Competition, CompetitionDate, Club, Nationality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_unique_id,
            swimmer_uniq_id,
            swimmer_name,
            age_to_record,
            data['stroke'],
            data['distance'],
            data['time'],
            data['competition'],
            data['competition_date'], # Stored as DD/MM/YYYY (Buddhist Year) string
            data['club'],
            data['nationality']
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"[DEBUG] Manual record for {data['name']} on {data['competition_date']} already exists. Skipping.")
        return False
    except Exception as e:
        print(f"[DEBUG] Error adding manual record: {e}")
        return False
    finally:
        conn.close()

def search_swimmers(name_query: str) -> pd.DataFrame:
    """Searches for swimmers by name (case-insensitive)."""
    if not name_query:
        return pd.DataFrame()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    query = "SELECT * FROM SwimmerTable WHERE Name LIKE ? ESCAPE '\\' LIMIT 10"
    df = pd.read_sql_query(query, conn, params=(f"%{name_query.replace('%', '\\%').replace('_', '\\_')}%",))
    conn.close()
    return df

def get_swimmer_by_name(name: str) -> pd.Series:
    """Fetches a single swimmer's details by their exact name."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM SwimmerTable WHERE Name = ?", conn, params=(name,))
    conn.close()
    if not df.empty:
        return df.iloc[0]
    return None

def search_competitions(name_query: str) -> list:
    """Searches for unique competition names by name (case-insensitive)."""
    if not name_query:
        return []
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    query = "SELECT DISTINCT Competition FROM RecordTable WHERE Competition LIKE ? ESCAPE '\\' LIMIT 10"
    c.execute(query, (f"%{name_query.replace('%', '\\%').replace('_', '\\_')}%",))
    results = [row[0] for row in c.fetchall()]
    conn.close()
    return results

def get_competition_date(competition_name: str) -> str:
    """Gets the most recent date string for a given competition."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT CompetitionDate FROM RecordTable WHERE Competition = ? AND CompetitionDate IS NOT NULL LIMIT 1", (competition_name,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def sync_records(df: pd.DataFrame):
    """
    Synchronizes the RecordTable with an edited DataFrame from a data editor.
    This function only performs UPDATES on existing records based on UniqueID.
    It does not allow adding or deleting records for safety.
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    updated_count = 0
    
    # These are the columns a user is allowed to edit.
    editable_columns = [
        'Age', 'Stroke', 'Distance', 'Time', 
        'Competition', 'CompetitionDate', 'Club', 'Nationality'
    ]

    for _, row in df.iterrows():
        unique_id = row.get('UniqueID')
        if not unique_id or pd.isna(unique_id):
            continue

        # Build the SET part of the SQL query dynamically
        set_clauses = []
        params = []
        for col in editable_columns:
            if col in row and not pd.isna(row[col]):
                set_clauses.append(f"{col} = ?")
                params.append(row[col])
        
        if not set_clauses:
            continue

        params.append(unique_id)
        
        sql = f"UPDATE RecordTable SET {', '.join(set_clauses)} WHERE UniqueID = ?"
        
        try:
            c.execute(sql, tuple(params))
            if c.rowcount > 0:
                updated_count += 1
        except sqlite3.Error as e:
            print(f"[ERROR] Failed to update record {unique_id}: {e}")

    conn.commit()
    conn.close()
    print(f"[DEBUG] Synced/updated {updated_count} records in the database.")
    return updated_count

def delete_records(unique_ids: list):
    """Deletes records from the RecordTable based on a list of UniqueIDs."""
    if not unique_ids:
        return 0
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Create placeholders for the IN clause
        placeholders = ','.join('?' for _ in unique_ids)
        query = f"DELETE FROM RecordTable WHERE UniqueID IN ({placeholders})"
        
        c.execute(query, unique_ids)
        deleted_count = c.rowcount
        conn.commit()
        
        print(f"[DEBUG] Deleted {deleted_count} records from the database.")
        return deleted_count
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to delete records: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


