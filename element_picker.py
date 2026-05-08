from selenium import webdriver
from selenium.webdriver.chrome.service import Service
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
# Recorder JS（多页面支持版本）
# =========================
def get_recorder_js(port):

    return f"""
(function () {{

// =========================
// 防重复注入（当前 document）
// =========================
if (window.__RPA_RECORDER__) {{
    return;
}}
window.__RPA_RECORDER__ = true;


// =========================
// stepIndex 和 currentPageIndex
// =========================
window.__stepIndex = window.__stepIndex || 0;
window.__currentPageIndex = window.__currentPageIndex || 0;
window.__pageHistory = window.__pageHistory || [window.location.href];


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
// 绑定事件（关键）
// =========================
function bind(win) {{

    if (!win.document || win.__bind_done) return;
    win.__bind_done = true;

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

        window.__stepIndex++;

        fetch("http://127.0.0.1:{port}/save_xpath", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json"
            }},
            body: JSON.stringify({{
                index: window.__stepIndex,
                page_index: window.__currentPageIndex,
                name,
                action,
                xpath,
                iframe: iframePath,
                value: "",
                url: window.location.href
            }})
        }});

    }}, true);

    // iframe递归
    let iframes = win.document.getElementsByTagName("iframe");

    for (let i = 0; i < iframes.length; i++) {{
        try {{
            bind(iframes[i].contentWindow);
        }} catch (e) {{}}
    }}
}}


// =========================
// 页面跳转检测（新增）
// =========================
function detectPageTransition() {{
    let lastUrl = window.location.href;
    
    setInterval(() => {{
        if (window.location.href !== lastUrl) {{
            console.log("🔄 页面已跳转:", lastUrl, "→", window.location.href);
            window.__currentPageIndex++;
            window.__pageHistory.push(window.location.href);
            lastUrl = window.location.href;
            
            // 重新绑定新页面元素
            setTimeout(() => {{
                bind(window);
                console.log("♻️ 新页面元素绑定完成");
            }}, 1000);
        }}
    }}, 500);
}}


// =========================
// ⭐ 核心修复：保活机制（解决跳转断录）
// =========================
function keepAlive() {{
    setInterval(() => {{
        try {{
            if (!window.__RPA_RECORDER__) {{
                window.__RPA_RECORDER__ = true;
                bind(window);
                console.log("♻️ recorder 自动恢复");
            }} else {{
                bind(window);
            }}
        }} catch (e) {{}}
    }}, 1500);
}}


// =========================
// 启动
// =========================
bind(window);
detectPageTransition();
keepAlive();

console.log("✅ RPA Recorder 多页面版已启动");

}})();
"""


# =========================
# 只注入一次（关键修复）
# =========================
def start_picker(url, port):

    options = webdriver.ChromeOptions()
    service = Service(get_driver_path())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    driver.get(url)
    time.sleep(2)

    # ⭐ 只注入一次（绝对关键）
    driver.execute_script(get_recorder_js(port))

    print("👉 录制器已启动")
    print("👉 支持多页面录制（页面跳转自动检测）")
    print("👉 关闭浏览器结束")

    while True:
        time.sleep(1)
