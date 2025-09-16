// characters.js 
import { checkToken, getToken, handleApiResponse } from "../../utils/auth.js";
import { showWaitingModal } from "./waiting.js";

document.addEventListener("DOMContentLoaded", () => {
    if (!checkToken()) return;
});

/** =========================================================
 *  A) 圖片分割／上傳
 *  openImageSplitModal()：只負責 head/body 分割，上傳到 /api/split-character
 * ========================================================= */
export function openImageSplitModal() {
    const modal = document.getElementById("uploadModal");
    const titleEl = document.getElementById("upload-title");
    const contentEl = document.getElementById("upload-step-content");
    const prevBtn = document.getElementById("upload-prev");
    const nextBtn = document.getElementById("upload-next");
    const previewModal = document.getElementById("previewModal");
    const previewImg = document.getElementById("previewImg");

    let files = [];

    const step = {
        title: "上傳並切割圖片",
        render: () => {
            contentEl.innerHTML = "";

            const section = document.createElement("div");
            section.className = "upload-section";

            const inner = document.createElement("div");
            inner.className = "upload-section-inner";
            section.appendChild(inner);

            if (files.length === 0) {
                const dropZone = document.createElement("div");
                dropZone.className = "upload-dropzone";
                dropZone.innerHTML = `
                    <img src="../../assets/icons/image-upload.png" class="upload-icon" />
                    <p>點擊新增或拖曳檔案到此區塊（每次處理 1 張）</p>
                    <input type="file" id="fileInput" accept="image/*" hidden />
                    <button id="uploadBtn">新增檔案</button>
                `;

                inner.appendChild(dropZone);

                const fileInput = dropZone.querySelector("#fileInput");
                const uploadBtn = dropZone.querySelector("#uploadBtn");

                uploadBtn.onclick = () => fileInput.click();
                fileInput.onchange = (e) => handleFiles(e.target.files);

                dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add("dragover"); };
                dropZone.ondragleave = () => dropZone.classList.remove("dragover");
                dropZone.ondrop = (e) => {
                    e.preventDefault();
                    dropZone.classList.remove("dragover");
                    handleFiles(e.dataTransfer.files);
                };
            } else {
                const list = document.createElement("div");
                list.className = "upload-file-list";

                files.forEach((f, idx) => {
                    const item = document.createElement("div");
                    item.className = "upload-file-item";
                    item.innerHTML = `
                        <img src="${f.dataUrl}" class="upload-thumb" />
                        <div class="upload-file-details">
                            <div class="upload-filename">${f.name}</div>
                            <div class="upload-filesize-preview">
                                <span class="upload-filesize">檔案大小：${(f.size / 1024).toFixed(1)} KB</span>
                                <button class="upload-preview-btn">預覽</button>
                            </div>
                        </div>
                        <button class="upload-remove-btn" data-i="${idx}">✕</button>
                    `;

                    item.querySelector(".upload-preview-btn").onclick = () => {
                        const previewModal = document.getElementById("previewModal");
                        const previewImg = document.getElementById("previewImg");

                        if (previewModal && previewModal.parentElement !== document.body) {
                            document.body.appendChild(previewModal);
                        }
                        previewImg.removeAttribute("style");
                        previewImg.classList.remove("preview-img");
                        previewImg.src = f.dataUrl;

                        document.body.classList.add("modal-open");
                        previewModal.style.display = "flex";
                    };

                    previewModal.onclick = (e) => {
                        if (e.target === previewModal) {
                            previewModal.style.display = "none";
                            document.body.classList.remove("modal-open");
                        }
                    };
                    item.querySelector(".upload-remove-btn").onclick = (e) => {
                        const i = +e.currentTarget.dataset.i;
                        files.splice(i, 1);
                        step.render();
                    };

                    list.appendChild(item);
                });

                inner.appendChild(list);

                const bottomBtnWrap = document.createElement("div");
                bottomBtnWrap.className = "upload-bottom-btn";

                const splitBtn = document.createElement("button");
                splitBtn.className = "upload-split-btn";
                splitBtn.textContent = "開始切割";

                splitBtn.onclick = () => {
                    const f = files[0];
                    openSplitModal(f.dataUrl, {
                        onConfirm: async ({ headBlob, bodyBlob }) => {
                            const suggested = f.name.replace(/\.[^.]+$/, "");
                            const fileName = prompt("請輸入此人物的名稱（不包含特殊符號）", suggested) || suggested || "char";
                            const safeBaseName = fileName;

                            const mainBlob = await (await fetch(f.dataUrl)).blob();

                            const fd = new FormData();
                            fd.append("filename", fileName);
                            fd.append("main", mainBlob, `${fileName}.png`);
                            fd.append("head", headBlob, `${fileName}_001.png`);
                            fd.append("body", bodyBlob, `${fileName}_002.png`);

                            const res = await fetch("/api/split-character", {
                                method: "POST",
                                headers: { Authorization: `Bearer ${getToken()}` },
                                body: fd,
                            });
                            const json = await handleApiResponse(res);
                            if (json) {
                                showToast("圖片上傳成功", "success");

                                const mainFile = json.main?.fileName || "";
                                const safeBase = mainFile.replace(/(_main|_head|_body)?\.(png|jpg|jpeg|webp)$/i, "");
                                console.log("✅ 圖片上傳成功！開始等待初始模型...");
                                showWaitingModal(json.upload_batch, safeBaseName);
                            }
                        }
                    });
                };

                bottomBtnWrap.appendChild(splitBtn);
                inner.appendChild(bottomBtnWrap);
            }

            contentEl.appendChild(section);
        }
    };

    function renderStep() {
        const titleEl = document.getElementById("upload-title");
        const prevBtn = document.getElementById("upload-prev");
        const nextBtn = document.getElementById("upload-next");

        let currentStep = 0;
        const steps = [step];

        titleEl.textContent = step.title;
        step.render();

        prevBtn.style.display = currentStep === 0 ? "none" : "inline-flex";
        prevBtn.onclick = () => {
            if (currentStep > 0) { currentStep--; renderStep(); }
        };

        nextBtn.onclick = () => {
            modal.style.display = "none";
        };
    }

    function handleFiles(selectedFiles) {
        const list = Array.from(selectedFiles || []);
        if (!list.length) return;
        const file = list[0];
        if (!file.type.startsWith("image/")) {
            showToast("僅支援圖片格式", "error");
            return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            files.push({
                name: file.name,
                size: file.size,
                dataUrl: e.target.result,
                rawFile: file,
            });
            renderStep();
        };
        reader.readAsDataURL(file);
    }

    async function openSplitModal(imageUrl, options = {}) {
        const splitModal = document.getElementById('splitModal');
        const splitCanvas = document.getElementById('splitCanvas');
        const cutLine = document.getElementById('splitCutLine');
        const percentEl = document.getElementById('splitPercent');
        const headPreview = document.getElementById('headPreview');
        const bodyPreview = document.getElementById('bodyPreview');
        const btnHalf = document.getElementById('btnHalf');
        const btn13 = document.getElementById('btn13') || document.getElementById('btnOneThird');
        const btn23 = document.getElementById('btn23') || document.getElementById('btnTwoThird');
        const btnConfirm = document.getElementById('btnConfirmSplit') || document.getElementById('confirmSplitBtn');
        const btnCancel = document.getElementById('btnCancelSplit') || document.getElementById('cancelSplitBtn');

        const ctx = splitCanvas.getContext('2d', { willReadFrequently: true });
        const img = new Image(); img.crossOrigin = 'anonymous';
        let splitCutY = 0, dragging = false;
        const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
        const getScaleY = () => splitCanvas.getBoundingClientRect().height / splitCanvas.height;

        function updateCutLine() {
            const topDisplay = splitCutY * getScaleY();
            cutLine.style.top = `${topDisplay}px`;
            const percent = Math.round((splitCutY / splitCanvas.height) * 100);
            if (percentEl) percentEl.textContent = `${percent}%`;
        }
        function updatePreview() {
            const w = splitCanvas.width, h = splitCanvas.height;
            const headCv = document.createElement('canvas'); headCv.width = w; headCv.height = splitCutY;
            const bodyCv = document.createElement('canvas'); bodyCv.width = w; bodyCv.height = h - splitCutY;
            if (headCv.height > 0) headCv.getContext('2d').drawImage(img, 0, 0, w, splitCutY, 0, 0, w, splitCutY);
            if (bodyCv.height > 0) bodyCv.getContext('2d').drawImage(img, 0, splitCutY, w, h - splitCutY, 0, 0, w, h - splitCutY);
            headPreview.src = headCv.height ? headCv.toDataURL('image/png') : '';
            bodyPreview.src = bodyCv.height ? bodyCv.toDataURL('image/png') : '';
        }
        function setRatio(r) { splitCutY = clamp(splitCanvas.height * r, 0, splitCanvas.height); updateCutLine(); updatePreview(); }
        async function buildBlobs() {
            const w = splitCanvas.width, h = splitCanvas.height;
            const headCv = document.createElement('canvas'); headCv.width = w; headCv.height = splitCutY;
            const bodyCv = document.createElement('canvas'); bodyCv.width = w; bodyCv.height = h - splitCutY;
            if (headCv.height > 0) headCv.getContext('2d').drawImage(img, 0, 0, w, splitCutY, 0, 0, w, splitCutY);
            if (bodyCv.height > 0) bodyCv.getContext('2d').drawImage(img, 0, splitCutY, w, h - splitCutY, 0, 0, w, h - splitCutY);
            const headBlob = await new Promise(res => headCv.toBlob(b => res(b), 'image/png'));
            const bodyBlob = await new Promise(res => bodyCv.toBlob(b => res(b), 'image/png'));
            return { headBlob, bodyBlob };
        }
        async function onConfirm() {
            const { headBlob, bodyBlob } = await buildBlobs();
            if (typeof options.onConfirm === 'function') options.onConfirm({ headBlob, bodyBlob, cutY: splitCutY, ratio: splitCutY / splitCanvas.height });
            splitModal.style.display = 'none';
            removeEvts();
        }

        function addEvts() {
            const onDown = () => (dragging = true);
            const onUp = () => (dragging = false);
            const onMove = (e) => {
                if (!dragging) return;
                const rect = splitCanvas.getBoundingClientRect();
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const yDisplay = clientY - rect.top;
                const ySource = yDisplay / getScaleY();
                splitCutY = clamp(ySource, 0, splitCanvas.height);
                updateCutLine(); updatePreview();
            };
            cutLine.addEventListener('mousedown', onDown);
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            cutLine.addEventListener('touchstart', onDown, { passive: true });
            document.addEventListener('touchmove', onMove, { passive: true });
            document.addEventListener('touchend', onUp, { passive: true });
            window._splitHandlers = { onDown, onMove, onUp };
            btnHalf?.addEventListener('click', () => setRatio(0.5));
            btn13?.addEventListener('click', () => setRatio(1 / 3));
            btn23?.addEventListener('click', () => setRatio(2 / 3));
            btnConfirm?.addEventListener('click', onConfirm);
            btnCancel?.addEventListener('click', () => { splitModal.style.display = 'none'; removeEvts(); });
        }
        function removeEvts() {
            const h = window._splitHandlers;
            if (!h) return;
            const { onDown, onMove, onUp } = h;
            const cutLine = document.getElementById('splitCutLine');
            const splitCanvas = document.getElementById('splitCanvas');
            cutLine?.removeEventListener('mousedown', onDown);
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            cutLine?.removeEventListener('touchstart', onDown);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
            btnConfirm?.removeEventListener?.('click', onConfirm);
        }

        img.onload = () => {
            splitCanvas.width = img.naturalWidth;
            splitCanvas.height = img.naturalHeight;
            const ctx2 = splitCanvas.getContext('2d');
            ctx2.clearRect(0, 0, splitCanvas.width, splitCanvas.height);
            ctx2.drawImage(img, 0, 0);
            splitModal.style.display = 'flex';
            setRatio(0.5);
            addEvts();
        };
        img.src = imageUrl;
    }

    previewModal.onclick = (e) => { if (e.target === previewModal) previewModal.style.display = "none"; };
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = "none"; };
    modal.style.display = "flex";

    titleEl.textContent = step.title;
    prevBtn.style.display = "none";
    nextBtn.textContent = "關閉";
    nextBtn.onclick = () => { modal.style.display = "none"; };
    step.render();
}

/** =========================================================
 *  B) 人物資訊與模型（新流程）
 *  openInfoUploadModal()：選既有主圖 → 模型/描述/語音
 *  後端：
 *   - POST /api/character-info   (imageId, profile?, memory?, voice?)
 *   - POST /api/upload-model     (imageId, model)
 * ========================================================= */
export function openInfoUploadModal() {
    const modal = document.getElementById("uploadModal");
    const titleEl = document.getElementById("upload-title");
    const contentEl = document.getElementById("upload-step-content");
    const prevBtn = document.getElementById("upload-prev");
    const nextBtn = document.getElementById("upload-next");

    const wizard = {
        imageId: null,
        profile: "",
        memory: "",
        voiceFile: null,
        modelFile: null,
        name: "",
        relation: "",
        particles: "",
        style: "",
        otherInfo: "",
    };


    // 組裝人物 json 格式
    function buildCharProfileJson() {
        const name = wizard.name || "";
        const relation = wizard.relation || "";
        const particles = wizard.particles || "";
        const style = wizard.style || "";
        const other = wizard.otherInfo || "";

        return JSON.stringify({
            name,
            prompt: `角色${name}是使用者的${relation}，經常用${particles}等語助詞。角色說話風格偏向${style}且口語化，另外角色也有以下特色${other}(如果你輸出的字數超過 10 字，句子數請控制在 1~2 句，請自動縮減為最自然的版本，且勿反問使用者問題，對於未知正確答案的問題請提出問題問使用者，並且切勿透漏自己是機器人的事實、如果使用者請求陪同做某件事、請答應參與)。`
        }, null, 2);
    }

    let current = 0;
    let bindingListLoading = false;

    const steps = [
        {
            title: "選擇主圖 1/5",
            render: () => {
                contentEl.innerHTML = "";

                const wrap = document.createElement("div");
                Object.assign(wrap.style, {
                    display: "flex", flexDirection: "column", alignItems: "center", gap: "12px",
                });

                const label = document.createElement("label");
                label.textContent = "選擇要綁定的人物主圖：";

                const selectEl = document.createElement("select");
                selectEl.id = "mainImageSelect";
                selectEl.style.minWidth = "220px";

                const hint = document.createElement("div");
                Object.assign(hint.style, { fontSize: "14px", color: "#666" });

                wrap.appendChild(label);
                wrap.appendChild(selectEl);
                wrap.appendChild(hint);
                contentEl.appendChild(wrap);

                nextBtn.disabled = true;
                bindingListLoading = true;

                loadMainImagesForBinding(selectEl, hint).then(() => {
                    if (wizard.imageId) selectEl.value = String(wizard.imageId);
                    wizard.imageId = selectEl.value || null;

                    bindingListLoading = false;
                    nextBtn.disabled = false;
                });

                selectEl.addEventListener("change", () => {
                    if (bindingListLoading) return;
                    wizard.imageId = selectEl.value || null;
                });
            }
        },
        {
            title: "關鍵人物資訊 2/5",
            render: () => {
                contentEl.innerHTML = `
                    <div class="form-group">
                        <label class="form-label">姓名</label>
                        <input type="text" id="charName" class="input-line" value="${wizard.name || ""}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">關係</label>
                        <input type="text" id="charRelation" class="input-line" value="${wizard.relation || ""}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">慣用語助詞</label>
                        <input type="text" id="charParticles" class="input-line" value="${wizard.particles || ""}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">人物說話風格</label>
                        <input type="text" id="charStyle" class="input-line" value="${wizard.style || ""}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">其他人物相關資訊</label>
                        <textarea id="charOtherInfo" rows="3" class="input-block">${wizard.otherInfo || ""}</textarea>
                    </div>
                    <div id="step2Error" style="color:#c00; font-weight:bold; font-size:16px; margin-top:6px; display:none;">⚠ 請完整填寫所有欄位</div>
                `;
                const bind = (id, key) => {
                    const el = document.getElementById(id);
                    el.oninput = (e) => {
                        wizard[key] = e.target.value.trim();
                        validateFields();
                    };
                };

                bind("charName", "name");
                bind("charRelation", "relation");
                bind("charParticles", "particles");
                bind("charStyle", "style");
                bind("charOtherInfo", "otherInfo");

                function validateFields() {
                    const required = ["name", "relation", "particles", "style", "otherInfo"];
                    const allFilled = required.every(k => wizard[k]?.trim().length > 0);
                    const errMsg = document.getElementById("step2Error");
                    const nextBtn = document.getElementById("upload-next");

                    if (!allFilled) {
                        errMsg.style.display = "block";
                        nextBtn.disabled = true;
                    } else {
                        errMsg.style.display = "none";
                        nextBtn.disabled = false;
                    }
                }

                validateFields();
            }
        },
        {
            title: "關鍵記憶與使用者記憶 3/5",
            render: () => {
                contentEl.innerHTML = `
                    <textarea id="memoryInput"
                    placeholder="請輸入相關記憶描述"
                    style="width:90%;height:100%;resize:none;font-size:18px;">${wizard.memory}</textarea>
                `;
                document.getElementById("memoryInput").oninput = e => (wizard.memory = e.target.value);
            }
        },
        {
            title: "語音上傳 4/5",
            render: () => {
                contentEl.innerHTML = `
                    <div class="upload-section" id="voiceDropzone">
                        <div class="upload-section-inner upload-dropzone" id="voiceUploadZone">
                            <div id="voicePreviewBox">
                                <img src="../../assets/icons/audio-upload.png" alt="Upload Icon" class="upload-icon" />
                                <p>點擊新增或拖曳語音檔案到此區塊（僅支援 .wav）</p>
                                <input type="file" id="voiceInput" accept=".wav" style="display:none;" />
                                <button id="uploadBtn">新增檔案</button>
                            </div>
                        </div>
                    </div>
                `;
                const uploadBtn = document.getElementById("uploadBtn");
                const voiceInput = document.getElementById("voiceInput");
                const dropzone = document.getElementById("voiceUploadZone");

                uploadBtn.addEventListener("click", () => voiceInput.click());

                const handleFileSelect = (file) => {
                    if (!file.name.endsWith(".wav")) {
                        showToast("僅支援 .wav 格式的語音檔", "error");
                        return;
                    }

                    wizard.voiceFile = file;

                    const sizeKB = (file.size / 1024).toFixed(1);
                    const audioURL = URL.createObjectURL(file);

                    dropzone.innerHTML = `
                        <div class="uploaded-card">
                            <img src="../../assets/icons/audio-icon.png" class="audio-icon" />
                            <div class="file-info">
                                <div class="filename">${file.name}</div>
                                <div class="filesize">檔案大小：${sizeKB} KB</div>
                            </div>
                            <button id="removeVoiceBtn" class="close-btn">✕</button>
                            <audio controls>
                                <source src="${audioURL}" type="audio/wav" />
                                您的瀏覽器不支援音訊播放。
                            </audio>
                        </div>
                    `;
                    document.getElementById("removeVoiceBtn").onclick = () => {
                        wizard.voiceFile = null;

                        dropzone.innerHTML = `
                            <div id="voicePreviewBox">
                                <img src="../../assets/icons/audio-upload.png" alt="Upload Icon" class="upload-icon" />
                                <p>點擊新增或拖曳語音檔案到此區塊（僅支援 .wav）</p>
                                <input type="file" id="voiceInput" accept=".wav" style="display:none;" />
                                <button id="uploadBtn">新增檔案</button>
                            </div>
                        `;
                        const newUploadBtn = document.getElementById("uploadBtn");
                        const newVoiceInput = document.getElementById("voiceInput");
                        newUploadBtn.onclick = () => newVoiceInput.click();
                        newVoiceInput.onchange = (e) => {
                            const file = e.target.files[0];
                            if (file) handleFileSelect(file);
                        };
                    };
                };

                voiceInput.addEventListener("change", e => {
                    const file = e.target.files[0];
                    if (file) handleFileSelect(file);
                });

                dropzone.addEventListener("dragover", e => {
                    e.preventDefault();
                    dropzone.classList.add("dragover");
                });

                dropzone.addEventListener("dragleave", () => {
                    dropzone.classList.remove("dragover");
                });

                dropzone.addEventListener("drop", e => {
                    e.preventDefault();
                    dropzone.classList.remove("dragover");

                    const file = e.dataTransfer.files[0];
                    if (file) {
                        voiceInput.files = e.dataTransfer.files;
                        handleFileSelect(file);
                    }
                });
            }
        },
        {
            title: "模型上傳 5/5",
            render: () => {
                contentEl.innerHTML = `
                    <div class="upload-section" id="modelDropWrap">
                        <div class="upload-section-inner upload-dropzone" id="modelDropzone">
                            <div id="modelEmptyBox">
                                <img src="../../assets/icons/model-upload.png" alt="Upload Icon" class="upload-icon" />
                                <p>點擊新增或拖曳人物模型到此區塊（僅支援 .fbx）</p>
                                <input type="file" id="modelInput" accept=".fbx" style="display:none;" />
                                <button id="uploadBtn">新增檔案</button>
                            </div>
                        </div>
                    </div>
                `;
                const modelDropzone = contentEl.querySelector("#modelDropzone");
                const modelChooseBtn = contentEl.querySelector("#uploadBtn");
                const modelInput = contentEl.querySelector("#modelInput");

                const rebindEmptyEvents = () => {
                    const chooseBtn = contentEl.querySelector("#uploadBtn");
                    const inputEl = contentEl.querySelector("#modelInput");
                    if (chooseBtn && inputEl) {
                        chooseBtn.onclick = () => inputEl.click();
                        inputEl.onchange = (e) => {
                            const f = e.target.files?.[0];
                            if (f) handleModelSelect(f);
                        };
                    }
                };

                const handleModelSelect = (file) => {
                    if (!/\.fbx$/i.test(file.name)) {
                        showToast("僅支援 .fbx 模型檔", "error");
                        return;
                    }
                    wizard.modelFile = file;

                    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);

                    modelDropzone.innerHTML = `
                        <div class="uploaded-card">
                            <img src="../../assets/icons/model-icon.png" class="audio-icon" />
                            <div class="file-info">
                                <div class="filename">${file.name}</div>
                                <div class="filesize">檔案大小：${sizeMB} MB</div>
                            </div>
                            <button id="removeModelBtn" class="close-btn">✕</button>
                        </div>
                    `;
                    const removeBtn = contentEl.querySelector("#removeModelBtn");
                    removeBtn && (removeBtn.onclick = () => {
                        wizard.modelFile = null;
                        modelDropzone.innerHTML = `
                            <div id="modelEmptyBox">
                                <img src="../../assets/icons/model-upload.png" alt="Upload Icon" class="upload-icon" />
                                <p>點擊新增或拖曳人物模型到此區塊（僅支援 .fbx）</p>
                                <input type="file" id="modelInput" accept=".fbx" style="display:none;" />
                                <button id="uploadBtn">新增檔案</button>
                            </div>
                        `;
                        rebindEmptyEvents();
                    });
                };

                if (modelChooseBtn && modelInput) {
                    modelChooseBtn.onclick = () => modelInput.click();
                    modelInput.onchange = (e) => {
                        const f = e.target.files?.[0];
                        if (f) handleModelSelect(f);
                    };
                }

                if (modelDropzone) {
                    modelDropzone.addEventListener("dragover", (e) => {
                        e.preventDefault();
                        modelDropzone.classList.add("dragover");
                    });
                    modelDropzone.addEventListener("dragleave", () => {
                        modelDropzone.classList.remove("dragover");
                    });
                    modelDropzone.addEventListener("drop", (e) => {
                        e.preventDefault();
                        modelDropzone.classList.remove("dragover");
                        const file = e.dataTransfer.files?.[0];
                        if (file) handleModelSelect(file);
                    });
                }
            }
        }
    ];

    async function renderStep() {
        titleEl.textContent = steps[current].title;
        const maybe = steps[current].render();
        if (maybe instanceof Promise) await maybe;
        prevBtn.style.display = current === 0 ? "none" : "inline-block";
        nextBtn.textContent = current === steps.length - 1 ? "儲存" : "▶";
    }

    prevBtn.onclick = () => {
        if (current > 0) { current--; renderStep(); }
    };

    nextBtn.onclick = async () => {
        if (current === 0 && !wizard.imageId) {
            showToast("請先選擇主圖", "error");
            return;
        }

        if (current < steps.length - 1) {
            current++;
            renderStep();
            return;
        }

        if (!wizard.memory?.trim()) {
            showToast("請輸入人物記憶描述", "error");
            return;
        }

        if (!wizard.voiceFile) {
            showToast("請選擇語音檔", "error");
            return;
        }
        if (!wizard.modelFile) {
            showToast("請選擇人物模型檔", "error");
            return;
        }

        try {
            wizard.profile = buildCharProfileJson();

            const fd1 = new FormData();
            fd1.append("imageId", String(wizard.imageId));
            fd1.append("profile", wizard.profile ?? "");
            fd1.append("memory", wizard.memory ?? "");
            if (wizard.voiceFile) fd1.append("voice", wizard.voiceFile);

            let res = await fetch("/api/character-info", {
                method: "POST",
                headers: { Authorization: `Bearer ${getToken()}` },
                body: fd1
            });

            if (!res.ok) {
                const txt = await res.text().catch(() => "");
                console.error("character-info error:", res.status, txt);
                showToast((txt && txt.slice(0, 180)) || "人物資訊上傳失敗", "error");
                return;
            }

            if (wizard.modelFile) {
                const extOk = /\.(fbx|glb|gltf)$/i.test(wizard.modelFile.name || "");
                if (!extOk) {
                    showToast("模型格式僅支援 .fbx ", "error");
                    return;
                }

                const fd2 = new FormData();
                fd2.append("model", wizard.modelFile);
                fd2.append("imageId", String(wizard.imageId));

                res = await fetch("/api/upload-model", {
                    method: "POST",
                    headers: { Authorization: `Bearer ${getToken()}` },
                    body: fd2
                });

                if (!res.ok) {
                    const txt = await res.text().catch(() => "");
                    console.error("upload-model error:", res.status, txt);
                    showToast(
                        (txt && txt.slice(0, 180)) || "模型上傳失敗，請確認已選擇模型與主圖",
                        "error"
                    );
                    return;
                }
            }

            showToast("人物資訊與模型已上傳成功", "success");
            modal.style.display = "none";
        } catch (err) {
            console.error("提交錯誤：", err);
            showToast("伺服器錯誤", "error");
        }
    };

    modal.onclick = (e) => { if (e.target === modal) modal.style.display = "none"; };
    modal.style.display = "flex";
    renderStep();

    function showToast(msg, type = "info") {
        window?.showToast ? window.showToast(msg, type) : alert(msg);
    }
}

/** ---------------------------
 * 取得主圖清單
 * -------------------------- */
async function fetchMainImages() {
    const res = await fetch("/api/files", {
        headers: { Authorization: `Bearer ${getToken()}` },
    });
    const data = await res.json().catch(() => ({}));
    const list = data.items || data.data || data || [];
    return Array.isArray(list) ? list : [];
}

async function loadMainImagesForBinding(selectEl, hintEl) {
    async function fetchList(url) {
        const res = await fetch(url, {
            headers: { Authorization: `Bearer ${getToken()}` },
            cache: "no-store",
        });
        if (!res.ok) return null;
        const text = await res.text();
        try { return JSON.parse(text); } catch { return null; }
    }

    let payload =
        await fetchList("/api/main-images-for-binding") ||
        await fetchList("/api/files/main-images-for-binding");

    const data = (payload && Array.isArray(payload.data)) ? payload.data : [];
    const list = data.filter(x => !x.has_model);

    selectEl.innerHTML = '<option value="">請選擇</option>';
    (list.length ? list : data).forEach(item => {
        const opt = document.createElement("option");
        opt.value = item.image_id;
        opt.textContent = item.file_name + (item.has_model ? "（已綁定）" : "");
        if (item.has_model && list.length) opt.disabled = true;
        selectEl.appendChild(opt);
    });

    if ((list.length ? list : data).length === 0) {
        hintEl.textContent = "目前沒有可綁定的主圖，請先到「圖片上傳」上傳並切割";
    } else {
        hintEl.textContent = "";
    }
}