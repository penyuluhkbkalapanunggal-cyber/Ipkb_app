from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import time

# =========================
# CONFIG
# =========================
USERNAME = os.getenv("NEWSIGA_USER")
PASSWORD = os.getenv("NEWSIGA_PASS")

if not USERNAME or not PASSWORD:
    raise Exception("Set NEWSIGA_USER dan NEWSIGA_PASS dulu")

# =========================
# CHROME OPTIONS
# =========================
options = Options()
options.add_argument("--start-maximized")

# optional
options.add_argument("--disable-blink-features=AutomationControlled")

# =========================
# OPEN BROWSER
# =========================
driver = webdriver.Chrome(options=options)

# =========================
# OPEN WEBSITE
# =========================
driver.get("https://newsiga-siga.bkkbn.go.id/#/beranda")

wait = WebDriverWait(driver, 30)

# =========================
# INPUT EMAIL
# =========================
email_input = wait.until(
    EC.element_to_be_clickable((By.ID, "email"))
)

email_input.clear()
email_input.send_keys(USERNAME)

# =========================
# INPUT PASSWORD
# =========================
password_input = wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
)

password_input.clear()
password_input.send_keys(PASSWORD)

# =========================
# CLICK LOGIN BUTTON
# =========================
login_button = wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
)

login_button.click()

# =========================
# WAIT AFTER LOGIN
# =========================
time.sleep(5)

print("LOGIN BERHASIL")

# browser tetap terbuka
input("Tekan ENTER untuk keluar...")

driver.quit()