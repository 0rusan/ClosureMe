// files.js
import { checkToken, getToken, handleApiResponse } from "../../utils/auth.js";

document.addEventListener("DOMContentLoaded", () => {
    if (!checkToken()) return;

    const fileCards = document.getElementById("fileCards");
    const goHomeBtn = document.getElementById("goHomeBtn");
    const searchInput = document.getElementById("searchInput");
    const sortSelect = document.getElementById("sortSelect");

    if (goHomeBtn) {
        goHomeBtn.addEventListener("click", () => {
            window.location.href = "/closureme/html/main.html";
        });
    }

    let allFiles = [];

    // 取得檔案資料
    async function loadFiles() {
        try {
            fileCards.innerHTML = "<p style='text-align:center;'>載入中...</p>";

            const res = await fetch("/api/files", {
                headers: { "Authorization": `Bearer ${getToken()}` }
            });

            const files = await handleApiResponse(res);
            if (!files) return;
            if (!res.ok) throw new Error(files.message || "無法取得資料");

            allFiles = files.data;
            renderFiles(allFiles);
        } catch (error) {
            console.error("載入錯誤:", error);
            fileCards.innerHTML = `<p style="color:red; text-align:center;">載入失敗：${error.message}</p>`;
        }
    }

    // 渲染檔案（套用搜尋 + 排序）
    function renderFiles(FileList) {
        let filteredFiles = [...FileList];

        const keyword = (searchInput.value || "").trim().toLowerCase();
        if (keyword) {
            filteredFiles = filteredFiles.filter(file =>
                (file.file_name || "").replace(/\.[^/.]+$/, "").toLowerCase().includes(keyword)
            );
        }

        const sortType = sortSelect.value;
        filteredFiles.sort((a, b) => {
            if (sortType === "time_desc") return new Date(b.uploaded_at) - new Date(a.uploaded_at);
            if (sortType === "time_asc") return new Date(a.uploaded_at) - new Date(b.uploaded_at);
            if (sortType === "name_asc") return a.file_name.localeCompare(b.file_name);
            if (sortType === "name_desc") return b.file_name.localeCompare(a.file_name);
            return 0;
        });

        fileCards.innerHTML = "";

        if (filteredFiles.length === 0) {
            fileCards.innerHTML = `<div class="empty-message">查無符合條件的角色</div>`;
            return;
        }

        filteredFiles.forEach(file => {
            const nameWithoutExt = (file.file_name || "").replace(/\.[^/.]+$/, "");

            const card = document.createElement("div");
            card.className = "file-card";
            card.innerHTML = `
                <img src="${file.image_path}" alt="${nameWithoutExt}">
                <div class="file-name">${nameWithoutExt}</div>
                <div class="file-time">${new Date(file.uploaded_at).toLocaleString()}</div>
                <div class="btn-group">
                    <button class="file-btn btn-download" data-url="${file.image_path}" data-filename="${nameWithoutExt}" data-label="圖片">圖片</button>
                    <button class="file-btn btn-download" data-url="${file.profile_path || ""}" data-filename="${nameWithoutExt}" data-label="關鍵人物資訊" ${file.profile_path ? "" : "disabled"}>資訊</button>
                    <button class="file-btn btn-download" data-url="${file.memory_path || ""}" data-filename="${nameWithoutExt}" data-label="記憶描述" ${file.memory_path ? "" : "disabled"}>記憶</button>
                </div>
                <div class="btn-group">
                    <button class="file-btn btn-rename" data-filename="${file.file_name}" data-upload-batch="${file.upload_batch}">重新命名</button>
                    <button class="file-btn btn-delete" data-name="${file.file_name}">刪除</button>
                </div>
            `;

            card.onclick = () => {
                if (file.image_id) {
                    localStorage.setItem("selectedCharacterId", file.image_id);
                    console.log(" 已選擇角色 ID：", file.image_id);
                } else {
                    console.warn(" 此角色沒有 image_id");
                }
            };

            fileCards.appendChild(card);

            const baseName = nameWithoutExt;
            const fbxUrl = `https://closureme-assets.s3.amazonaws.com/fbx/temp/${baseName}_init.fbx`;

            fetch(fbxUrl, { method: "HEAD" }).then(res => {
                if (res.ok) {
                    const fbxBtn = document.createElement("a");
                    fbxBtn.href = fbxUrl;
                    fbxBtn.download = `${baseName}.fbx`;
                    fbxBtn.className = "file-btn btn-download";
                    fbxBtn.textContent = "初始模型";
                    const btnGroup = card.querySelector(".btn-group");
                    if (btnGroup) {
                        btnGroup.insertAdjacentElement("beforeend", fbxBtn);
                    }
                }
            });
        });

        bindDownloadButtons();
        bindRenameButtons();
        bindDeleteButtons();
    }

    function getBaseName(fileNameWithExt = "") {
        let base = fileNameWithExt.replace(/\.[^/.]+$/, "");
        base = base.replace(/\.(profile|memory)$/i, "");
        base = base.replace(/_00[12]$/i, "");
        return base;
    }

    // 下載按鈕事件
    function bindDownloadButtons() {
        document.querySelectorAll(".btn-download").forEach(btn => {
            btn.onclick = async () => {
                const url = btn.dataset.url;
                const label = btn.dataset.label;
                const fileName = btn.dataset.filename;

                if (!url || !url.startsWith("http")) {
                    showToast("找不到檔案路徑！", "error");
                    return;
                }

                if (confirm(`是否確定下載 ${fileName} 的${label}？`)) {
                    try {
                        const rawExt = url.split(".").pop().split("?")[0];
                        const ext = rawExt && rawExt.length <= 5
                            ? rawExt
                            : (label === "圖片" ? "png" : "json");

                        let suffix = "";
                        if (label === "關鍵人物資訊") suffix = "_profile";
                        else if (label === "記憶描述") suffix = "_memory";

                        const saveName = (label === "圖片")
                            ? `${fileName}.png`
                            : `${fileName}${suffix}.${ext}`;

                        if (label === "圖片") {
                            const proxyUrl = `/api/proxy-download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(saveName)}`;
                            window.location.href = proxyUrl;
                        } else {
                            const res = await fetch(url);
                            if (!res.ok) throw new Error("下載失敗");
                            const blob = await res.blob();
                            const blobUrl = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = blobUrl;
                            a.download = saveName;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(blobUrl);
                        }
                    } catch (error) {
                        console.error("下載錯誤：", error);
                        showToast("下載失敗", "error");
                    }
                }
            };
        });
    }

    function bindRenameButtons() {
        document.querySelectorAll(".btn-rename").forEach(btn => {
            btn.onclick = async (e) => {
                const button = e.currentTarget;
                const uploadBatch = button.getAttribute("data-upload-batch");
                const fileNameWithExt = button.getAttribute("data-filename") || "";
                const fileName = getBaseName(fileNameWithExt);

                const inputName = prompt("輸入新的人物名稱：")?.trim();
                if (!inputName) return;
                const newName = inputName.replace(/\s+/g, "_");

                const payload = uploadBatch ? { uploadBatch, newName } : { fileName, newName };

                try {
                    const res = await fetch(`/api/rename-character`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${getToken()}`
                        },
                        body: JSON.stringify(payload)
                    });

                    const data = await handleApiResponse(res);
                    if (!data) return;
                    if (!res.ok) throw new Error(data.message);
                    showToast("重新命名成功", "success");
                    loadFiles();
                } catch (error) {
                    showToast("重新命名失敗", "error");
                }
            };
        });
    }

    function bindDeleteButtons() {
        document.querySelectorAll(".btn-delete").forEach(btn => {
            btn.onclick = async () => {
                const fileNameWithExt = btn.dataset.name || "";
                const fileName = getBaseName(fileNameWithExt);
                if (!fileName) {
                    showToast("找不到要刪除的檔名", "error");
                    return;
                }
                if (!confirm(`確定要刪除角色 ${fileName} 嗎？`)) return;

                try {
                    const res = await fetch("/api/delete-character", {
                        method: "DELETE",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${getToken()}`
                        },
                        body: JSON.stringify({ fileName })
                    });
                    const data = await handleApiResponse(res);
                    if (!data) return;
                    if (!res.ok) throw new Error(data.message);
                    showToast("刪除成功", "success");
                    loadFiles();
                } catch (error) {
                    showToast("刪除失敗", "error");
                }
            };
        });
    }

    searchInput.addEventListener("input", () => renderFiles(allFiles));
    sortSelect.addEventListener("change", () => renderFiles(allFiles));

    loadFiles();
});