import requests
from bs4 import BeautifulSoup
import os
import json

# --- CONFIGURATION ---
URL = "https://www.teslafi.com/firmware.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}
MEMORY_FILE = "memory.json"
WAVE_THRESHOLD = 5  # Trigger "Wave Alert" if installs increase by 5+ in 10 mins

# Secrets
bot_token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("CHAT_ID")

def send_telegram(message):
    if not bot_token or not chat_id:
        print("Error: Missing Telegram tokens.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Failed to send alert: {e}")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)

def check_teslafi():
    print("Fetching TeslaFi data...")
    try:
        response = requests.get(URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Connection error: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    
    # --- LOGIC: Find the First Row of the Fleet Table ---
    latest_version = None
    current_count = 0
    
    # We look for the first table row that has a version number
    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if not cols: continue
        
        text = cols[0].get_text().strip()
        
        # Valid version check (Starts with '20' and has a dot, e.g., '2025.44.1')
        if text.startswith("20") and "." in text and len(text) < 25:
            latest_version = text
            
            # The "Count" is usually in the 2nd column (index 1)
            try:
                count_text = cols[1].get_text().strip().replace(",", "")
                current_count = int(count_text)
            except:
                current_count = 0
            
            # We found the top row, stop searching
            break

    if not latest_version:
        print("Could not find version data. Structure may have changed.")
        return

    # --- COMPARE WITH MEMORY ---
    memory = load_memory()
    last_version = memory.get("last_version", "None")
    last_count = memory.get("last_count", 0)

    print(f"Current: {latest_version} ({current_count} installs)")
    print(f"Saved:   {last_version} ({last_count} installs)")

    # --- DECISION TREE ---

    # SCENARIO 1: NEW BUILD (Version Changed)
 if latest_version != last_version:
    detail_url = f"https://www.teslafi.com/firmware.php?detail={latest_version}"
    msg = (
        f"🆕 **New Build** – `{latest_version}`\n"
        f" Initial Rollout to {current_count} on [TeslaFi]({detail_url})"
    )
    send_telegram(msg)

        
        # Save both new version and new count
        memory["last_version"] = latest_version
        memory["last_count"] = current_count
        save_memory(memory)

    # SCENARIO 2: WAVE (Same Version, Big Jump in Count)
    elif current_count >= last_count + WAVE_THRESHOLD:
    diff = current_count - last_count
    msg = (
        f"A new wave of `{latest_version}` is rolling out now.\n"
        f"Initial Rollout Size: {diff}"
    )
    send_telegram(msg)
        
        # Update the count only
        memory["last_count"] = current_count
        save_memory(memory)

    else:
        print("No significant change.")
        # (Optional) Update count silently so we track small increments?
        # memory["last_count"] = current_count
        # save_memory(memory)

if __name__ == "__main__":
    check_teslafi()
