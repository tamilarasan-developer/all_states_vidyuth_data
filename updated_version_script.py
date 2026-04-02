import re
import os
import time
import json
import shutil
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import mysql.connector

STATES = [
    {
        "name": "TamilNadu",
        "url": "https://vidyutpravah.in/state-data/tamil-nadu",
        "current_xpath": '//*[@id="TamilNadu_map"]/div[6]/span/span',
        "yesterday_xpath": '//*[@id="TamilNadu_map"]/div[4]/span/span',
    },
    {
        "name": "Rajasthan",
        "url": "https://vidyutpravah.in/state-data/rajasthan",
        "current_xpath": '//*[@id="Rajasthan_map"]/div[6]/span/span',
        "yesterday_xpath": '//*[@id="Rajasthan_map"]/div[4]/span/span',
    },
    {
        "name": "Maharashtra",
        "url": "https://vidyutpravah.in/state-data/maharashtra",
        "current_xpath": '//*[@id="Maharastra_map"]/div[6]/span/span',
        "yesterday_xpath": '//*[@id="Maharastra_map"]/div[4]/span/span',
    },
    {
        "name": "Karnataka",
        "url": "https://vidyutpravah.in/state-data/karnataka",
        "current_xpath": '//*[@id="Karnataka_map"]/div[6]/span/span',
        "yesterday_xpath": '//*[@id="Karnataka_map"]/div[4]/span/span',
    },
    {
        "name": "AndhraPradesh",
        "url": "https://vidyutpravah.in/state-data/andhra-pradesh",
        "current_xpath": '//*[@id="AndraPradesh_map"]/div[6]/span/span',
        "yesterday_xpath": '//*[@id="AndraPradesh_map"]/div[4]/span/span',
    }
]

XPATH_TIME_BLOCK = '/html/body/table/tbody/tr[1]/td/table/tbody/tr[2]/td/table/tbody/tr/td[2]'


def get_db_connection():
    db_user = os.getenv("DB_USER", "tamil")
    db_password = os.getenv("DB_PASSWORD", "Tamil@321")
    db_name = os.getenv("DB_NAME", "vidyuthdata")
    db_port = int(os.getenv("DB_PORT", "3306"))

    # Try env host first, then common Docker/Linux host routes.
    hosts_to_try = []
    for host in [
        os.getenv("DB_HOST", "host.docker.internal"),
        "host.docker.internal",
        "172.17.0.1",
        "127.0.0.1",
        "localhost",
    ]:
        if host and host not in hosts_to_try:
            hosts_to_try.append(host)

    last_error = None
    for host in hosts_to_try:
        try:
            return mysql.connector.connect(
                host=host,
                user=db_user,
                password=db_password,
                database=db_name,
                port=db_port,
                connection_timeout=10,
            )
        except Exception as e:
            last_error = e
            print(f"⚠️ DB connect failed on host '{host}': {e}")

    raise last_error


def normalize_mw_value(raw_text):
    """Convert values like '17,104\u00a0MW' to integer MW (17104)."""
    cleaned = str(raw_text).replace("\u00a0", " ").strip().upper()
    match = re.search(r"([\d,]+)\s*MW", cleaned)
    if not match:
        raise ValueError(f"Unable to parse MW value from: {raw_text}")
    return int(match.group(1).replace(",", ""))


def block_resources(route):
    if route.request.resource_type in ["image", "stylesheet", "font"]:
        route.abort()
    else:
        route.continue_()


def get_run_folders():
    now = datetime.now()

    # Format exactly as requested: YYYY-MM-DD HH-MM-SS
    run_folder = now.strftime("%Y-%m-%d %H-%M-%S")

    # Base path: downloads/2026-03-27 12-29-02 (removed 'vidyuthdata')
    base_path = os.path.join("downloads", run_folder)

    screenshot_folder = os.path.join(base_path, "screenshots")
    json_folder = os.path.join(base_path, "json")

    # Create the folders
    os.makedirs(screenshot_folder, exist_ok=True)
    os.makedirs(json_folder, exist_ok=True)

    return screenshot_folder, json_folder, now.strftime("%Y%m%d_%H%M%S")

def scrape_state(page, state, folder_path):
    try:
        print(f"\n⚡ Loading {state['name']}...")

        for attempt in range(3):
            try:
                page.goto(state["url"], timeout=90000, wait_until="commit")
                break
            except:
                print(f"Retry {attempt+1} for {state['name']}")
                time.sleep(3)

        page.wait_for_selector(f'xpath={state["current_xpath"]}', timeout=60000)

        current = page.locator(f'xpath={state["current_xpath"]}').inner_text()
        yesterday = page.locator(f'xpath={state["yesterday_xpath"]}').inner_text()
        current_mw = normalize_mw_value(current)
        yesterday_mw = normalize_mw_value(yesterday)

        full_text = page.locator(f'xpath={XPATH_TIME_BLOCK}').inner_text()
        full_text = " ".join(full_text.split())

        match = re.search(
            r"TIME BLOCK (\d{2}:\d{2} - \d{2}:\d{2}) DATED (\d{2} [A-Z]{3} \d{4})",
            full_text
        )

        if match:
            time_block = match.group(1).replace(" - ", "-")
            date_obj = datetime.strptime(match.group(2), "%d %b %Y").date()
        else:
            print(f"❌ Parsing failed for {state['name']}")
            return None

        timestamp = datetime.now().strftime("%H-%M-%S")
        filepath = os.path.join(folder_path, f"{state['name']}_{timestamp}.png")

        page.screenshot(path=filepath, full_page=False)

        print(f"📸 Screenshot saved: {filepath}")

        print(f"✅ {state['name']} DATA:")
        print("Current   :", f"{current_mw} MW")
        print("Yesterday :", f"{yesterday_mw} MW")
        print("TimeBlock :", time_block)
        print("Date      :", date_obj)

        return {
            "state": state["name"],
            "current_demand_mw": current_mw,
            "yesterday_demand_mw": yesterday_mw,
            "time_block": time_block,
            "date": str(date_obj),
            "captured_at": datetime.now().isoformat(timespec="seconds")
        }

    except Exception as e:
        print(f"❌ Error in {state['name']}:", e)
        return None
    

def cleanup_old_files(base_path, days=2):
    """Delete directories older than specified days."""
    try:
        if not os.path.exists(base_path):
            return
        
        now = datetime.now()
        cutoff_time = now - timedelta(days=days)
        
        for folder_name in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder_name)
            
            if os.path.isdir(folder_path):
                folder_mtime = datetime.fromtimestamp(os.path.getmtime(folder_path))
                
                if folder_mtime < cutoff_time:
                    print(f"🗑️ Deleting old folder: {folder_path}")
                    shutil.rmtree(folder_path)
                    print(f"✅ Deleted: {folder_name}")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")


def insert_into_db(data):
    try:
        conn = get_db_connection()

        cursor = conn.cursor()

        query = """
        INSERT INTO demand_data (
            state, current_demand, yesterday_demand,
            time_block, date, captured_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            data["state"],
            data["current_demand_mw"],
            data["yesterday_demand_mw"],
            data["time_block"],
            data["date"],
            data["captured_at"]
        )

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        print("✅ Saved to DB:", data["state"])

    except Exception as e:
        print("❌ DB Error:", e)


def main():
    start = time.time()
    current_now = datetime.now().astimezone()
    print(f"🕒 Local time: {current_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Clean up files older than 2 days before starting new scrape
    cleanup_old_files("downloads", days=2)
    
    # Unpack the 3 variables returned by get_run_folders()
    screenshot_folder, json_folder, run_timestamp = get_run_folders()
    output_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox"]
        )

        context = browser.new_context()
        context.route("**/*", block_resources)

        pages = {}

        for state in STATES:
            page = context.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            pages[state["name"]] = page

        for state in STATES:
            row = scrape_state(pages[state["name"]], state, screenshot_folder)
            if row:
                output_rows.append(row)
                insert_into_db(row)

        browser.close()

    # Save the JSON file specifically into the json_folder
    output_file = os.path.join(json_folder, f"state_demand_{run_timestamp}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_rows, f, indent=4)

    print(f"\n📝 JSON saved: {output_file}")
    print(f"📁 Screenshots folder: {screenshot_folder}")
    print(f"📁 JSON folder: {json_folder}")

    print(f"\n🚀 Total Time: {round(time.time() - start, 2)} seconds")
    print("🚀 Script started at:", current_now.strftime("%H:%M:%S %Z"))


if __name__ == "__main__":
    main()