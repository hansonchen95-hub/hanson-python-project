from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import sys
import time


# =========================
# driver路径
# =========================
def get_driver_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'chromedriver.exe')
    return os.path.join(os.getcwd(), 'chromedriver.exe')


# =========================
# Recorder JS（跨页面持久化版本）
# =========================
def get_recorder_js(port):

    return f"""
(function () {{

// =========================
// ⭐ 跨页面保持状态（window.name）
// =========================
if (!window.__RPA_STEP_INDEX__) {{
    window.__RPA_STEP_INDEX__ = 0;
}}
if (!window.__RPA_PAGE_INDEX__) {{
    window.__RPA_PAGE_INDEX__ = 0;
}}

// 从 window.name 恢复状态
try {{
    let savedState = window.name ? JSON.parse(window.name) : {{}};
    if (savedState.stepIndex !== undefined) {{
        window.__RPA_STEP_INDEX__ = savedState.stepIndex;
        console.log(`✅ 恢复状态: 步数=${{window.__RPA_STEP_INDEX__}}, 页数=${{window.__RPA_PAGE_INDEX__}}`);
    }}
    if (savedState.pageIndex !== undefined) {{
        window.__RPA_PAGE_INDEX__ = savedState.pageIndex;
    }}
}} catch (e) {{
    console.warn("恢复状态失败:", e);
}}


// =========================
// XPath
// =========================
function getXPath(el) {{
    if (!el) return "";

    if (el.id) return '//*[@id="' + el.id + '"]';
    if (el === document.body) return '/html/body';

    let ix = 0;
    let siblings = el.parentNode ? el.parentNode.childNodes : [];

    for (let i = 0; i < siblings.length; i++) {{
        let sib = siblings[i];

        if (sib === el) {{
            return getXPath(el.parentNode)
                + '/' + el.tagName.toLowerCase()
                + '[' + (ix + 1) + ']';
        }}

        if (sib.nodeType === 1 && sib.tagName === el.tagName) {{
            ix++;
        }}
    }}
}}


// =========================
// iframe路径
// =========================
function getIframePath(win) {{
    let path = [];

    try {{
        while (win !== window.top) {{
            let parent = win.parent;
            let iframes = parent.document.getElementsByTagName("iframe");

            for (let i = 0; i < iframes.length; i++) {{
                if (iframes[i].contentWindow === win) {{
                    path.unshift("iframe[" + i + "]");
                    break;
                }}
            }}

            win = parent;
        }}
    }} catch (e) {{}}

    return path.join(">");
}}


// =========================
// 保存状态到 window.name
// =========================
function saveState() {{
    try {{
        window.name = JSON.stringify({{
            stepIndex: window.__RPA_STEP_INDEX__,
            pageIndex: window.__RPA_PAGE_INDEX__
        }});
    }} catch (e) {{
        console.warn("保存状态失败:", e);
    }}
}}


// =========================
// 绑定事件
// =========================
function bind(win) {{

    if (!win.document || win.__rpa_bound__) return;
    win.__rpa_bound__ = true;

    win.document.addEventListener("mousedown", function(e) {{

        let el = e.target;
        if (!el) return;

        let xpath = getXPath(el);
        let iframePath = getIframePath(win);
        let tag = el.tagName ? el.tagName.toLowerCase() : "";

        let action = "click";
        let type = (el.type || "").toLowerCase();

        if (
            (tag === "input" && ["text","password","email","number"].includes(type)) ||
            tag === "textarea"
        ) {{
            action = "input";
        }} else if (tag === "select") {{
            action = "select";
        }}

        let name =
            el.innerText ||
            el.placeholder ||
            el.name ||
            el.id ||
            tag;

        el.style.outline = "3px solid red";

        window.__RPA_STEP_INDEX__++;
        saveState();

        console.log(`✅ 录制: [${{window.__RPA_PAGE_INDEX__}}页-步${{window.__RPA_STEP_INDEX__}}] ${{name}}`);

        fetch("http://127.0.0.1:{port}/save_xpath", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json"
            }},
            body: JSON.stringify({{
                index: window.__RPA_STEP_INDEX__,
                page_index: window.__RPA_PAGE_INDEX__,
                name,
                action,
                xpath,
                iframe: iframePath,
                value: "",
                url: window.location.href
            }})
        }}).catch(e => console.warn("发送步骤失败:", e));

    }}, true);

    // iframe递归绑定
    let iframes = win.document.getElementsByTagName("iframe");
    for (let i = 0; i < iframes.length; i++) {{
        try {{
            bind(iframes[i].contentWindow);
        }} catch (e) {{}}
    }}
}}


// =========================
// 定期重新绑定（保证新页面也有事件）
// =========================
function keepAlive() {{
    setInterval(() => {{
        try {{
            // 清除旧的绑定标记，强制重新绑定
            window.__rpa_bound__ = false;
            bind(window);
        }} catch (e) {{
            console.warn("保活检查异常:", e);
        }}
    }}, 3000);
}}


// =========================
// 启动
// =========================
bind(window);
keepAlive();

console.log("✅ RPA Recorder 已启动");

}})();
"""


# =========================
# 启动录制器（Selenium 版本 - 支持页面跳转）
# =========================
def start_picker(url, port):

    print("\n" + "="*70)
    print("🚀 启动 RPA 录制器")
    print("="*70 + "\n")

    options = webdriver.ChromeOptions()
    
    # 禁用沙箱模式（某些系统需要）
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(get_driver_path())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    driver.get(url)
    time.sleep(2)

    # 第一次注入脚本
    driver.execute_script(get_recorder_js(port))
    print("✅ 初始页面脚本已注入\n")

    # ⭐ 关键：监听页面加载，重复注入脚本
    print("📌 监听页面跳转中...\n")
    
    last_url = driver.current_url
    no_change_count = 0
    injection_count = 1

    try:
        while True:
            try:
                time.sleep(1)
                
                current_url = driver.current_url
                
                # 检测 URL 变化
                if current_url != last_url:
                    print(f"\n🔄 检测到页面跳转: {last_url} → {current_url}")
                    last_url = current_url
                    
                    # 等待新页面加载
                    try:
                        WebDriverWait(driver, 5).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )
                    except:
                        pass
                    
                    time.sleep(1)
                    
                    # ⭐ 重新注入脚本
                    try:
                        driver.execute_script(get_recorder_js(port))
                        injection_count += 1
                        print(f"✅ 新页面脚本已注入 (第 {injection_count} 次)")
                        print(f"✅ 页面标记: page_index++")
                        
                        # 更新页面索引
                        driver.execute_script("""
                            window.__RPA_PAGE_INDEX__++;
                            window.name = JSON.stringify({
                                stepIndex: window.__RPA_STEP_INDEX__,
                                pageIndex: window.__RPA_PAGE_INDEX__
                            });
                            console.log(`页面递增到: ${{window.__RPA_PAGE_INDEX__}}`);
                        """)
                        
                        no_change_count = 0
                    except Exception as e:
                        print(f"❌ 脚本注入失败: {e}")
                
                # 检查浏览器是否还打开
                try:
                    driver.current_window_handle
                except:
                    print("\n❌ 浏览器已关闭")
                    break
                    
            except Exception as e:
                print(f"⚠️  异常: {e}")
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹️  录制已停止")
    finally:
        try:
            driver.quit()
        except:
            pass
        
        print("\n" + "="*70)
        print("✅ 录制器已关闭")
        print("="*70 + "\n")
