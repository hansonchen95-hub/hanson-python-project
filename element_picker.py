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
# Recorder JS（跨页面持久化版本）
# =========================
def get_recorder_js(port):

    return f"""
(function () {{

// =========================
// ⭐ 跨页面保持状态（关键修复）
// =========================
if (!window.__RPA_STEP_INDEX__) {{
    window.__RPA_STEP_INDEX__ = 0;
}}
if (!window.__RPA_PAGE_INDEX__) {{
    window.__RPA_PAGE_INDEX__ = 0;
}}
if (!window.__RPA_PAGE_HISTORY__) {{
    window.__RPA_PAGE_HISTORY__ = [];
}}

// 在 window.name 中保存状态（即使页面跳转也不会丢失）
try {{
    let savedState = window.name ? JSON.parse(window.name) : {{}};
    if (savedState.stepIndex) {{
        window.__RPA_STEP_INDEX__ = savedState.stepIndex;
        window.__RPA_PAGE_INDEX__ = savedState.pageIndex;
        window.__RPA_PAGE_HISTORY__ = savedState.pageHistory || [];
    }}
}} catch (e) {{}}


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
// 保存当前状态到 window.name
// =========================
function saveState() {{
    try {{
        window.name = JSON.stringify({{
            stepIndex: window.__RPA_STEP_INDEX__,
            pageIndex: window.__RPA_PAGE_INDEX__,
            pageHistory: window.__RPA_PAGE_HISTORY__
        }});
    }} catch (e) {{
        console.warn("保存状态失败:", e);
    }}
}}


// =========================
// 绑定事件（关键）
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
        
        // 保存状态
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
        }}).catch(e => console.warn("发送失败:", e));

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
// ⭐ 页面跳转监听（MutationObserver + URL 变化）
// =========================
function setupPageTransitionDetection() {{
    let lastUrl = window.location.href;
    
    // 方案1: 监听 URL 变化
    const checkUrlChange = setInterval(() => {{
        if (window.location.href !== lastUrl) {{
            console.log(`🔄 页面跳转: ${{lastUrl}} → ${{window.location.href}}`);
            window.__RPA_PAGE_INDEX__++;
            window.__RPA_PAGE_HISTORY__.push(window.location.href);
            lastUrl = window.location.href;
            saveState();
            
            // 延迟重新绑定（等待新页面加载）
            setTimeout(() => {{
                // 清除旧的绑定标记
                delete document.__proto__.__rpa_bound__;
                window.__rpa_bound__ = false;
                
                bind(window);
                console.log(`✅ 新页面绑定完成 [${{window.__RPA_PAGE_INDEX__}}页]`);
            }}, 800);
        }}
    }}, 300);
    
    // 方案2: beforeunload 前保存状态
    window.addEventListener("beforeunload", () => {{
        saveState();
    }});
    
    // 方案3: 监听 hashchange（支持 SPA 应用）
    window.addEventListener("hashchange", () => {{
        console.log("🔄 Hash变化检测到");
        window.__RPA_PAGE_INDEX__++;
        window.__RPA_PAGE_HISTORY__.push(window.location.href);
        saveState();
        
        setTimeout(() => {{
            window.__rpa_bound__ = false;
            bind(window);
            console.log(`✅ 新页面绑定完成 [${{window.__RPA_PAGE_INDEX__}}页]`);
        }}, 500);
    }});
}}


// =========================
// 定期检查和恢复（保活机制）
// =========================
function keepAlive() {{
    setInterval(() => {{
        try {{
            // 定期重新绑定（防止事件丢失）
            bind(window);
            
            // 检查状态是否在 window.name 中
            try {{
                let savedState = window.name ? JSON.parse(window.name) : {{}};
                if (savedState.stepIndex && savedState.stepIndex > window.__RPA_STEP_INDEX__) {{
                    window.__RPA_STEP_INDEX__ = savedState.stepIndex;
                }}
            }} catch (e) {{}}
        }} catch (e) {{
            console.warn("保活检查异常:", e);
        }}
    }}, 2000);
}}


// =========================
// 启动录制器
// =========================
bind(window);
setupPageTransitionDetection();
keepAlive();

console.log("✅ RPA Recorder 已启动");
console.log(`📊 初始状态 - 步数: ${{window.__RPA_STEP_INDEX__}}, 页数: ${{window.__RPA_PAGE_INDEX__}}`);

}})();
"""


# =========================
# 启动录制器
# =========================
def start_picker(url, port):

    print("\n" + "="*70)
    print("🚀 启动 RPA 录制器")
    print("="*70 + "\n")

    options = webdriver.ChromeOptions()
    service = Service(get_driver_path())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    driver.get(url)
    time.sleep(2)

    # ⭐ 注入脚本
    driver.execute_script(get_recorder_js(port))

    print("✅ 录制器已启动，功能说明：\n")
    print("  📌 自动检测页面跳转")
    print("  📝 支持多页面录制")
    print("  🖱️  点击任意元素自动记录")
    print("  ⌨️  输入框会自动识别")
    print("  💾 步骤自动发送到服务器")
    print("\n⏸️  关闭浏览器即可结束录制\n")
    print("="*70 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️  录制已停止")
    finally:
        try:
            driver.quit()
        except:
            pass
