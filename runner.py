import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    WebDriverException
)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import os
import sys


# =========================
# driver path
# =========================
def get_driver_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'chromedriver.exe')
    return os.path.join(os.getcwd(), 'chromedriver.exe')


# =========================
# 等待元素（稳定核心）
# =========================
def find_element_safe(driver, xpath, iframe_path=None, timeout=10):

    try:
        driver.switch_to.default_content()

        # iframe支持（如果有）
        if iframe_path:
            try:
                if "iframe[" in iframe_path:
                    indexes = iframe_path.split(">")
                    for item in indexes:
                        idx = int(item.replace("iframe[", "").replace("]", ""))
                        iframe = driver.find_elements(By.TAG_NAME, "iframe")[idx]
                        driver.switch_to.frame(iframe)
            except Exception:
                pass

        wait = WebDriverWait(driver, timeout)

        element = wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

        return element

    except TimeoutException:
        return None


# =========================
# click（防DOM变化）
# =========================
def safe_click(driver, element):

    try:
        element.click()
        return True

    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False


# =========================
# input（防stale）
# =========================
def safe_input(driver, element, value):

    try:
        element.clear()
    except Exception:
        pass

    try:
        element.send_keys(value)
        return True
    except StaleElementReferenceException:
        return False
    except Exception:
        try:
            driver.execute_script(
                "arguments[0].value=arguments[1];",
                element,
                value
            )
            return True
        except Exception:
            return False


# =========================
# 执行单步（核心稳定逻辑）
# =========================
def execute_step(driver, step):

    xpath = step.get("xpath")
    action = step.get("action")
    value = step.get("value", "")
    iframe = step.get("iframe", "")

    for retry in range(3):  # ⭐ 关键：重试3次

        try:
            print(f"执行: {step.get('name')}")

            element = find_element_safe(
                driver,
                xpath,
                iframe
            )

            if not element:
                print("未找到元素，重试")
                time.sleep(1)
                continue

            if action == "input":
                ok = safe_input(driver, element, value)
            else:
                ok = safe_click(driver, element)

            if ok:
                return True

            time.sleep(1)

        except WebDriverException as e:

            # ⭐ window关闭保护
            if "no such window" in str(e):
                print("浏览器窗口已关闭，终止任务")
                return False

            print("WebDriver异常重试:", e)
            time.sleep(1)

        except Exception as e:
            print("执行异常:", e)
            time.sleep(1)

    print("步骤失败:", step)
    return False


# =========================
# 主执行入口（稳定版）
# =========================
def run_task(config_path):

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    driver = webdriver.Chrome(
        service=Service(get_driver_path())
    )

    try:
        driver.get(config["login_url"])
        time.sleep(2)

        steps = config.get("steps", [])

        for step in steps:

            ok = execute_step(driver, step)

            if not ok:
                print("❌ 执行失败，停止任务")
                break

            time.sleep(1)

    except Exception as e:
        print("任务异常:", e)

    finally:
        try:
            driver.quit()
        except:
            pass