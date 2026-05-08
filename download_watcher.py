import os
import time


def wait_download_complete(download_path, timeout=60):
    start = time.time()

    while True:
        files = os.listdir(download_path)

        # Chrome未完成下载的标志
        temp_files = [f for f in files if f.endswith(".crdownload")]

        if not temp_files and len(files) > 0:
            return True

        if time.time() - start > timeout:
            return False

        time.sleep(1)