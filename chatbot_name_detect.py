#!/usr/bin/env python3

import time, re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup

# ───────────────────────────────────────── BASIC CONFIG ─────────────────────────────────────────
SITES = [ 
    "https://www.axisbank.com",     # Axis AHA
    "https://www.hdfcbank.com",     # EVA
    "https://www.icicibank.com/",   # iPal
    "https://www.irctc.co.in/nget/train-search",  # AskDISHA
    "https://www.bankofbaroda.in/",
]

CHROMEDRIVER_PATH = "/home/khushi/Test_case/Chatbot/chromedriver"
CHROME_BINARY_PATH = "/usr/bin/google-chrome"
HEADLESS = True

VENDOR_HINTS = [
    'intercom', 'drift', 'zendesk', 'livechat', 'tidio',
    'hubspot', 'salesforceliveagent', 'freshchat', 'corover',
    'userlike', 'manychat', 'chatwoot', 'zoho', 'chatbot'
]

CHAT_KEYWORDS = [
    "chat", "bot", "virtual assistant", "how can i help", "live help", "chatbot", "Let's talk", "talk"
]

NAME_PATTERNS = [
    re.compile(r"\b(?:hi|hello)[\s,.!]*(?:i\s+am|i['’]?m)\s+(?P<name>[A-Z][a-zA-Z0-9]{2,})", re.I),
    re.compile(r"\b(?:my name is|this is)\s+(?P<name>[A-Z][a-zA-Z0-9]{2,})", re.I),
    re.compile(r"\b(?:chat with|ask|talk to|say hi to)\s+(?P<name>[A-Z][a-zA-Z0-9]{2,})", re.I),
    re.compile(r"\b(?P<name>[A-Z][a-zA-Z0-9]{2,})\s+(chatbot|assistant|bot)", re.I),
    re.compile(r"\b(chatbot|assistant|bot)\s+(?P<name>[A-Z][a-zA-Z0-9]{2,})", re.I),
    re.compile(r"\bwelcome to\s+(?P<name>[A-Z][a-zA-Z0-9]{2,})", re.I),
    re.compile(r'chat with ["“](?P<name>[A-Z][a-zA-Z0-9]+)["”]', re.I),
    re.compile(r"\b(?:chat|chatting|talking)\s+with\s+(our\s+)?(?:assistant|bot|ai)?\s*(?P<name>[A-Z][a-zA-Z0-9]+)", re.I),
    re.compile(r"\b(?P<name>[A-Z][a-zA-Z0-9]{2,})\s+(is here to help|is here|is online)", re.I),
    re.compile(r"need help\?\s+(?P<name>[A-Z][a-zA-Z0-9]+)\s+is here", re.I),
    re.compile(r"\bmeet\s+(our\s+)?(?:ai|chatbot|virtual\s+assistant)?\s*(?P<name>[A-Z][a-zA-Z0-9]+)", re.I),
    re.compile(r"you're chatting with\s+(?P<name>[A-Z][a-zA-Z0-9]+)", re.I),
    re.compile(r"this conversation is handled by\s+(?P<name>[A-Z][a-zA-Z0-9]+)", re.I),
    re.compile(r"\byou are now connected with\s+(?P<name>[A-Z][a-zA-Z0-9]+)", re.I),
]

STOPWORDS = {w.lower() for w in [
    "the", "official", "python", "website", "assistant", "support",
    "page", "team", "bot", "chatbot", "help", "virtual", "service",
    "bank", "your", "and", "this", "that", "name", "internet", "account",
    "online", "all", "services", "information","Let's talk", "talk",
    "rewards", "advisor", "menu", "login", "home", "business", "mortgage"
]}

# ───────────────────────────────────────── MAIN FUNCTION ────────────────────────────────────────
def identify_chatbot_and_name(driver, url: str) -> str:
    print(f"\n🔍 Checking: {url}")
    bot_detected, bot_name = False, None

    def safe_click(elem):
        try:
            elem.click()
        except Exception:
            driver.execute_script("arguments[0].click();", elem)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(2)

        launcher_xpath = (
            "//*[" +
            "contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or " +
            "contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'help') or " +
            "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'ask disha') or " +
            "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or " +
            "contains(@class,'chat') or contains(@class,'help')" +
            "]"
        )
        if (launchers := driver.find_elements(By.XPATH, launcher_xpath)):
            print("💬 Found launcher button — clicking...")
            safe_click(launchers[0])
            time.sleep(2)

        target_soup = None

        # Step 3: Scan vendor or custom iframes
        for frame in driver.find_elements(By.TAG_NAME, "iframe"):
            src = (frame.get_attribute("src") or frame.get_attribute("data-src") or "").lower()
            if any(v in src for v in VENDOR_HINTS):
                print(f"📦 Found vendor/custom iframe: {src}")
                _force_iframe_load(driver, frame)
                if _switch_and_mark(frame, driver):
                    target_soup = BeautifulSoup(driver.page_source, "html.parser")
                    bot_detected = True
                    break
                driver.switch_to.default_content()

        # Step 4: Fallback to all iframes
        if not bot_detected:
            for frame in driver.find_elements(By.TAG_NAME, "iframe"):
                _force_iframe_load(driver, frame)
                if _switch_and_mark(frame, driver):
                    print("📦 Found possible chat iframe (non-vendor)")
                    target_soup = BeautifulSoup(driver.page_source, "html.parser")
                    bot_detected = True
                    break
                driver.switch_to.default_content()

        # Step 5: Scan main page as fallback
        if not bot_detected:
            print("🧠 Fallback to main page scan")
            target_soup = BeautifulSoup(driver.page_source, "html.parser")
            if _looks_like_chat(target_soup):
                print("✅ Detected chat keywords on main page")
                bot_detected = True
            else:
                print("🕵️ No visual indicators, proceeding with metadata scan")

        # Step 6: Extract bot name
        if target_soup:
            visible = " ".join(t.strip() for t in target_soup.stripped_strings)
            title_text = (target_soup.title.string or "") if target_soup.title else ""
            meta_desc = target_soup.find("meta", attrs={"name": "description"})
            meta_desc = meta_desc.get("content", "") if meta_desc else ""
            visible += " " + title_text + " " + meta_desc

            print("🔍 Visible text used for name detection:")
            print("────────────────────────────────────")
            print(visible[:1000] + "..." if len(visible) > 1000 else visible)
            print("────────────────────────────────────")

            for pat in NAME_PATTERNS:
                if (m := pat.search(visible)):
                    candidate = m.group("name").strip()
                    if candidate.lower() not in STOPWORDS:
                        bot_name = candidate
                        print(f"🎯 Matched name pattern: {candidate}")
                        break

        driver.switch_to.default_content()

        if bot_name:
            return f"✅ Chatbot found: Name appears to be '{bot_name}'"
        elif bot_detected:
            return "✅ Chatbot detected (name unknown)"
        else:
            return "❌ No chatbot indicators found"

    except Exception as e:
        return f"⚠️ Error checking {url}: {e}"


# ─────────────────────────────────── HELPERS ───────────────────────────────────
def _switch_and_mark(frame, driver) -> bool:
    try:
        driver.switch_to.frame(frame)
        time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        return _looks_like_chat(soup)
    except Exception:
        return False

def _looks_like_chat(soup: BeautifulSoup) -> bool:
    text = " ".join(t.strip() for t in soup.stripped_strings).lower()
    class_names = " ".join(" ".join(tag.get("class", [])) for tag in soup.find_all(True)).lower()
    return any(k in text or k in class_names for k in CHAT_KEYWORDS)

def _force_iframe_load(driver, frame):
    if not frame.get_attribute("src") and frame.get_attribute("data-src"):
        print("⚙️ Forcing lazy iframe load via data-src...")
        driver.execute_script("arguments[0].setAttribute('src', arguments[1]);", frame, frame.get_attribute("data-src"))
        time.sleep(2)


# ─────────────────────────────────── ENTRY POINT ───────────────────────────────────
if __name__ == "__main__":
    chrome_opts = Options()
    chrome_opts.binary_location = CHROME_BINARY_PATH
    if HEADLESS:
        chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=chrome_opts)

    try:
        for site in SITES:
            print(identify_chatbot_and_name(driver, site))
    finally:
        driver.quit()
