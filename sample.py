import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

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
    }
]

XPATH_TIME_BLOCK = '/html/body/table/tbody/tr[1]/td/table/tbody/tr[2]/td/table/tbody/tr/td[2]'


def scrape_state(page, state):
    try:
        print(f"\n🔄 Loading {state['name']}...")

        page.goto(state["url"], timeout=90000, wait_until="domcontentloaded")

        # Wait for element
        page.wait_for_selector(f'xpath={state["current_xpath"]}', timeout=30000)

        current = page.locator(f'xpath={state["current_xpath"]}').inner_text()
        yesterday = page.locator(f'xpath={state["yesterday_xpath"]}').inner_text()

        full_text = page.locator(f'xpath={XPATH_TIME_BLOCK}').inner_text()
        full_text = " ".join(full_text.split())

        match = re.search(
            r"TIME BLOCK (\d{2}:\d{2} - \d{2}:\d{2}) DATED (\d{2} [A-Z]{3} \d{4})",
            full_text
        )

        if match:
            time_block = match.group(1)
            date_obj = datetime.strptime(match.group(2), "%d %b %Y").date()
        else:
            print(f"❌ Parsing failed for {state['name']}")
            return

        print(f"✅ {state['name']} DATA:")
        print("Current   :", current)
        print("Yesterday :", yesterday)
        print("TimeBlock :", time_block)
        print("Date      :", date_obj)

    except Exception as e:
        print(f"❌ Error in {state['name']}:", e)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox"]
        )  # ✅ silent mode # visible browser

        pages = {}

        # Open tabs
        for state in STATES:
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            pages[state["name"]] = page

        # Scrape each tab
        for state in STATES:
            scrape_state(pages[state["name"]], state)

        print("\n🎯 Done. Browser will stay open for 20 seconds...")
        time.sleep(20)

        browser.close()


if __name__ == "__main__":
    main()