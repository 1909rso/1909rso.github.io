import pandas as pd
import json
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from bs4 import BeautifulSoup


def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    return driver


def load_whoscored_events_data(match_centre_url):
    try:
        driver = get_driver()
        driver.get(match_centre_url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        page_source = driver.page_source
        driver.quit()

        soup = BeautifulSoup(page_source, "html.parser")
        script_tag = soup.select_one('script:-soup-contains("matchCentreData")')

        if not script_tag:
            print("No script tag with matchCentreData found")
            return None

        _, _, json_text = script_tag.text.partition("matchCentreData: ")
        match_json = json.loads(json_text.split(",\n")[0])

        player_id_name_dict = match_json.get("playerIdNameDictionary", {})
        events_dict = match_json.get("events", {})

        if not events_dict:
            print("No events data found")
            return None

        df = pd.json_normalize(events_dict)

        if "playerId" in df.columns:
            df["playerName"] = df["playerId"].apply(
                lambda x: player_id_name_dict.get(str(int(x))) if pd.notna(x) else None
            )

        if "relatedPlayerId" in df.columns:
            df["relatedPlayerName"] = df["relatedPlayerId"].apply(
                lambda x: player_id_name_dict.get(str(int(x))) if pd.notna(x) else None
            )

        return df, match_json

    except Exception as e:
        print(f"Error: {e}")
        return None, None


def extract_summary(match_json, df):
    """Extract key stats and events for the web page."""

    home = match_json.get("home", {})
    away = match_json.get("away", {})

    # Goals
    goals = []
    if df is not None and "type.displayName" in df.columns:
        goal_events = df[df["type.displayName"] == "Goal"]
        for _, row in goal_events.iterrows():
            goals.append({
                "player": row.get("playerName", "Unknown"),
                "minute": int(row.get("minute", 0)),
                "teamId": int(row.get("teamId", 0)) if pd.notna(row.get("teamId")) else 0,
            })

    # Cards
    cards = []
    if df is not None and "type.displayName" in df.columns:
        card_events = df[df["type.displayName"].isin(["YellowCard", "RedCard", "YellowRedCard"])]
        for _, row in card_events.iterrows():
            cards.append({
                "player": row.get("playerName", "Unknown"),
                "minute": int(row.get("minute", 0)),
                "type": row.get("type.displayName", ""),
                "teamId": int(row.get("teamId", 0)) if pd.notna(row.get("teamId")) else 0,
            })

    # Shots
    shots_home = 0
    shots_away = 0
    if df is not None and "type.displayName" in df.columns:
        shot_types = ["Goal", "ShotOnPost", "SavedShot", "MissedShots"]
        shots = df[df["type.displayName"].isin(shot_types)]
        home_id = home.get("teamId")
        shots_home = len(shots[shots["teamId"] == home_id])
        shots_away = len(shots[shots["teamId"] != home_id])

    # Passes
    passes_home = 0
    passes_away = 0
    if df is not None and "type.displayName" in df.columns:
        passes = df[df["type.displayName"] == "Pass"]
        home_id = home.get("teamId")
        passes_home = len(passes[passes["teamId"] == home_id])
        passes_away = len(passes[passes["teamId"] != home_id])

    summary = {
        "homeTeam": home.get("name", "Home"),
        "awayTeam": away.get("name", "Away"),
        "homeScore": home.get("scores", {}).get("fulltime", 0),
        "awayScore": away.get("scores", {}).get("fulltime", 0),
        "homeTeamId": home.get("teamId"),
        "awayTeamId": away.get("teamId"),
        "goals": goals,
        "cards": cards,
        "stats": {
            "shotsHome": shots_home,
            "shotsAway": shots_away,
            "passesHome": passes_home,
            "passesAway": passes_away,
        },
        "lastUpdated": pd.Timestamp.now().isoformat(),
    }

    return summary


def main():
    # ⚠️ CAMBIA ESTA URL por la del partido que quieras
    match_url = "https://1xbet.whoscored.com/matches/1980125/live/international-int-friendly-2026-haiti-new-zealand"

    # Si se pasa URL como argumento: python scrape_match.py <url>
    if len(sys.argv) > 1:
        match_url = sys.argv[1]

    print(f"Scraping: {match_url}")
    df, match_json = load_whoscored_events_data(match_url)

    if df is not None and match_json is not None:
        summary = extract_summary(match_json, df)

        # Guardar JSON para la página web
        with open("data/match_data.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print("✅ Datos guardados en data/match_data.json")
        print(f"   {summary['homeTeam']} {summary['homeScore']} - {summary['awayScore']} {summary['awayTeam']}")
    else:
        print("❌ No se pudieron cargar los datos")
        sys.exit(1)


if __name__ == "__main__":
    main()
