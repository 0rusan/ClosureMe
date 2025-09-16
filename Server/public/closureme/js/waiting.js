// waiting.js
export function showWaitingModal(uploadBatch, safeBaseName, customTitle = "初始模型生成中...") {
    const modal = document.createElement("div");
    modal.className = "waiting-modal";

    modal.innerHTML = `
        <div class="waiting-box">
            <h2 class="waiting-title">${customTitle}</h2>
            <p class="waiting-subtitle">角色名稱：<span class="char-name">${safeBaseName || "unknown"}</span></p>
            <div class="waiting-bar">
                <div class="waiting-bar-fill"></div>
            </div>
            <button class="btn-cancel">取消等待</button>
        </div>
    `;

    document.body.appendChild(modal);
    const cancelBtn = modal.querySelector(".btn-cancel");

    let polling = true;
    let retryCount = 0;
    const intervalMs = 3000;
    const maxRetry = 600;

    async function checkModel() {
        if (!polling) return;
        const url = `https://closureme-assets.s3.ap-east-2.amazonaws.com/fbx/temp/${safeBaseName}_init.fbx`;
        console.log(`📡 檢查：${url}（第 ${retryCount + 1}/${maxRetry} 次）`);

        try {
            const res = await fetch(url, { method: "HEAD", cache: "no-store" });

            if (res.ok) {
                console.log("✅ 模型檔案已偵測到：", url);
                polling = false;

                const box = modal.querySelector(".waiting-box");
                box.innerHTML = `
                    <h2 class="waiting-title">初始模型已就緒</h2>
                    <p class="waiting-subtitle">角色名稱：<span class="char-name">${safeBaseName || "unknown"}</span></p>
                    <div class="waiting-actions">
                        <button class="btn-download">下載初始模型</button>
                        <button class="btn-skip">取消</button>
                    </div>
                `;

                const downloadBtn = box.querySelector(".btn-download");
                const skipBtn = box.querySelector(".btn-skip");

                downloadBtn.onclick = () => {
                    let w = null;
                    try { w = window.open(url, "_blank", "noopener"); } catch { }
                    if (!w) {
                        const a = document.createElement("a");
                        a.href = url;
                        a.target = "_blank";
                        a.rel = "noopener";
                        a.style.display = "none";
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }

                    setTimeout(() => {
                        modal.remove();
                        window.location.href = "/closureme/html/main.html";
                    }, 1200);
                };

                skipBtn.onclick = () => {
                    modal.remove();
                    window.location.href = "/closureme/html/main.html";
                };

                return;
            }
        } catch (err) {
            console.debug("⚠️ HEAD 檢查失敗，稍後重試", err);
        }

        retryCount++;
        if (retryCount < maxRetry) {
            setTimeout(checkModel, intervalMs);
        } else {
            alert("⚠️ 等待超時，請稍後再試！");
            modal.remove();
            window.location.href = "/closureme/html/main.html";
        }
    }

    cancelBtn.onclick = () => {
        polling = false;
        modal.remove();
        window.location.href = "/closureme/html/main.html";
    };

    setTimeout(checkModel, 800);
}

window.showWaitingModal = showWaitingModal;