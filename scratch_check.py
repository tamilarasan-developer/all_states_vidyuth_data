from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
    page = browser.new_page()
    page.goto("https://vidyutpravah.in/state-data/rajasthan")
    try:
        page.wait_for_selector('//*[@id="Rajasthan_map"]/div[6]/span/span', timeout=10000)
        print("Found it!")
    except Exception as e:
        print("Timeout.")
        print(page.content()[:1000]) # Print beginning of HTML
        page.screenshot(path="rajasthan_error.png")
    browser.close()
