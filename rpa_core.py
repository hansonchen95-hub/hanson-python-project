from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from download_watcher import wait_download_complete
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import time
import os
import sys


# ===== driver =====
def get_driver_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'chromedriver.exe')
    return os.path.join(os.getcwd(), 'chromedriver.exe')


def create_driver(download_dir):
    options = webdriver.ChromeOptions()

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }

    options.add_experimental_option("prefs", prefs)

    service = Service(get_driver_path())

    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ===== 主执行 =====
def run_task(task):
    driver = create_driver(task["download_path"])
    wait = WebDriverWait(driver, 20)

    try:
        print("打开登录页")
        driver.get(task["login_url"])

        wait.until(EC.presence_of_element_located((By.XPATH, task["username_xpath"])))

        driver.find_element(By.XPATH, task["username_xpath"]).send_keys(task["username"])
        driver.find_element(By.XPATH, task["password_xpath"]).send_keys(task["password"])
        driver.find_element(By.XPATH, task["login_btn_xpath"]).click()

        input("👉 如果有验证码，请手动输入后按回车继续...")

        print("进入导出页面")
        driver.get(task["export_url"])

        wait.until(EC.element_to_be_clickable((By.XPATH, task["export_btn_xpath"])))
        driver.find_element(By.XPATH, task["export_btn_xpath"]).click()

        print("开始下载...")

        ok = wait_download_complete(task["download_path"])

        if ok:
            print("✅ 下载完成")
        else:
            print("❌ 下载超时")

    except Exception as e:
        print("错误:", e)

    finally:
        driver.quit()