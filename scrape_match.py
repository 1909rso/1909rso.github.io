import pandas as pd
import json
import sys
import time
import random
from bs4 import BeautifulSoup


def get_driver():
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-GB")
    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver


def load_whoscored_events_data(match_centre_url):
    driver = None
    try:
        driver = get_driver()

        # Visitar Google primero para parecer más humano
        driver.get("https://www.google.com")
        time.sleep(random.uniform(2, 4))

        driver.get(match_centre_url)

        # Esperar que cargue el contenido dinámico
        time.sleep(random.uniform(8, 12))

        # Scroll suave para simular comportamiento humano
        driver.execute_script("window.scrollTo(0, 300)")
        time.sleep(1)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        script_tag = soup.select_one('script:-soup-contains("matchCentreData")')

        if not script_tag:
            print("No script tag with matchCentreData found")
            # Guardar HTML para debug
            with open("debug_page.html", "w") as f:
                f.write(page_source[:5000])
            return None, None

        _, _, json_text = script_tag.text.partition("matchCentreData: ")
        match_json = json.loads(json_text.split(",\n")[0])

        player_id_name_dict = match_json.get("playerIdNameDictionary", {})
        events_dict = match_json.get("events", {})

        if not events_dict:
            print("No events data found")
            return None, None

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
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def extract_summary(match_json, df):
    home = match_json.get("home", {})
    away = match_json.get("away", {})

    goals = []
    cards = []
    shots_home = shots_away = passes_home = passes_away = 0
    home_id = home.get("teamId")

    if df is not None and "type.displayName" in df.columns:
        goal_events = df[df["type.displayName"] == "Goal"]
        for _, row in goal_events.iterrows():
            goals.append({
                "player": row.get("playerName", "Unknown"),
                "minute": int(row.get("minute", 0)),
                "teamId": int(row.get("teamId", 0)) if pd.notna(row.get("teamId")) else 0,
            })

        card_events = df[df["type.displayName"].isin(["YellowCard", "RedCard", "YellowRedCard"])]
        for _, row in card_events.iterrows():
            cards.append({
                "player": row.get("playerName", "Unknown"),
                "minute": int(row.get("minute", 0)),
                "type": row.get("type.displayName", ""),
                "teamId": int(row.get("teamId", 0)) if pd.notna(row.get("teamId")) else 0,
            })

        shot_types = ["Goal", "ShotOnPost", "SavedShot", "MissedShots"]
        shots = df[df["type.displayName"].isin(shot_types)]
        shots_home = len(shots[shots["teamId"] == home_id])
        shots_away = len(shots[shots["teamId"] != home_id])

        passes = df[df["type.displayName"] == "Pass"]
        passes_home = len(passes[passes["teamId"] == home_id])
        passes_away = len(passes[passes["teamId"] != home_id])

    return {
        "homeTeam": home.get("name", "Home"),
        "awayTeam": away.get("name", "Away"),
        "homeScore": home.get("scores", {}).get("fulltime", 0),
        "awayScore": away.get("scores", {}).get("fulltime", 0),
        "homeTeamId": home_id,
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


def main():
    # ⚠️ CAMBIA ESTA URL por la del partido que quieras
    match_url = "https://1xbet.whoscored.com/matches/1980125/live/international-int-friendly-2026-haiti-new-zealand"

    if len(sys.argv) > 1:
        match_url = sys.argv[1]

    print(f"Scraping: {match_url}")
    df, match_json = load_whoscored_events_data(match_url)

    if df is not None and match_json is not None:
        summary = extract_summary(match_json, df)

        import os
        os.makedirs("data", exist_ok=True)
        with open("data/match_data.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print("✅ Datos guardados en data/match_data.json")
        print(f"   {summary['homeTeam']} {summary['homeScore']} - {summary['awayScore']} {summary['awayTeam']}")
    else:
        print("❌ No se pudieron cargar los datos")
        sys.exit(1)


if __name__ == "__main__":
    main()
