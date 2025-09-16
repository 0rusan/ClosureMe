import { openImageSplitModal, openInfoUploadModal } from './characters.js';
import { runTTS } from "./tts.js";
import { runAnalysisTxt } from "./analysis.js";
import { showWaitingModal } from './waiting.js';

const charScroll = document.getElementById("char-scroll");
const sceneScroll = document.getElementById("scene-scroll");
const displayArea = document.querySelector(".display-area");
const logoutBtn = document.getElementById("logoutBtn");

window.addEventListener("DOMContentLoaded", () => {
  localStorage.removeItem("selectedCharacterId");
  localStorage.removeItem("selectedCharacterName");
  localStorage.removeItem("selectedEnvironment");
});

document.getElementById("imageBtn")?.addEventListener("click", () => {
  openImageSplitModal();
});

document.getElementById("generateBtn").addEventListener("click", async () => {
  const imageId = localStorage.getItem("selectedCharacterId");
  const fileName = localStorage.getItem("selectedCharacterName");
  const envIndex = imageData.scene.selected;
  const environment = imageData.scene.envValues?.[envIndex];

  if (!imageId || !fileName) {
    showToast("請先選擇角色", "error");
    return;
  }

  if (!environment) {
    showToast("請先選擇場景", "error");
    return;
  }

  function authHeaders() {
    return {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${localStorage.getItem("token")}`
    };
  }

  const safeBaseName = fileName;
  showWaitingModal(null, safeBaseName, "資源加載中，請稍候...");

  await fetch("/api/write-index", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ fileName })
  });

  try {
    const [voiceRes, modelRes, profileRes, memoryRes, envRes] = await Promise.all([
      fetch("/api/download-voice", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ imageId })
      }),
      fetch("/api/download-model", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ fileName })
      }),
      fetch("/api/download-profile", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ fileName })
      }),
      fetch("/api/download-memory", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ fileName })
      }),
      fetch("/api/write-environment", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ environment })
      })
    ]);

    if (!voiceRes.ok) return showToast("語音下載失敗", "error");
    if (!modelRes.ok) return showToast("模型下載失敗", "error");
    if (!profileRes.ok) return showToast("資訊下載失敗", "error");
    if (!memoryRes.ok) return showToast("記憶下載失敗", "error");
    if (!envRes.ok) return showToast("環境檔寫入失敗", "error");

    await runTTS();
    await runAnalysisTxt();
   
    showToast("成功載入所有人物資源與環境", "success");
    const waitingModal = document.querySelector(".waiting-modal");
    if (waitingModal) waitingModal.remove();
  } catch (err) {
    console.error(err);
    showToast("發生錯誤", "error");
  }
});

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    window.location.href = "/";
  });
}

const imageData = {
  char: { images: [], names: [], memoryDescriptions: [], imageIds: [], selected: null, timestamp: null },
  scene: {
    images: [
      "../../assets/scenes/meeting-room.png",
      "../../assets/scenes/park.png",
      "../../assets/scenes/library.png"
    ],
    names: ["會議室", "公園", "圖書館"],
    envValues: ["MeetingRoom", "Park", "Library"],
    descriptions: ["書架靜立，光影柔和，心緒在此慢慢沉澱下來", "陽光灑落，笑聲迴盪，讓心在遊戲與奔跑中釋放與療癒", "簡潔的空間裡，思緒被收攏，讓心重新找回秩序與力量"],
    selected: null,
    timestamp: null
  }
};

async function loadCharacters() {
  try {
    const token = localStorage.getItem("token");
    const res = await fetch("/api/characters", {
      headers: { "Authorization": `Bearer ${token}` },
      cache: "no-store"
    });
    if (!res.ok) throw new Error("無法載入角色資料");
    const payload = await res.json();
    const data = Array.isArray(payload.data) ? payload.data : [];
    charScroll.innerHTML = "";

    if (data.length === 0) {
      addUploadButton();
      return;
    }

    imageData.char.images = [];
    imageData.char.names = [];
    imageData.char.memoryDescriptions = [];
    imageData.char.imageIds = [];

    for (let i = 0; i < data.length; i++) {
      const char = data[i];
      const card = createCard("char", i, char.image_path);
      charScroll.appendChild(card);

      imageData.char.images.push(char.image_path);
      imageData.char.names.push(char.file_name);
      imageData.char.imageIds.push(char.image_id);

      const memoryText = await loadTextFile(char.memory_path);
      imageData.char.memoryDescriptions.push(memoryText);
    }

    document.getElementById("char-count").textContent = `0/${imageData.char.images.length}`;
    addUploadButton();
  } catch (err) {
    console.error("角色載入錯誤:", err);
    charScroll.innerHTML = "<p style='color:red;'>無法載入角色資料</p>";
    addUploadButton();
  }
}

async function loadTextFile(url) {
  if (!url) return "描述檔案不存在";
  try {
    const res = await fetch(url);
    if (!res.ok) return "描述讀取失敗";
    const txt = await res.text();
    try {
      const j = JSON.parse(txt);
      return j?.content ?? txt;
    } catch { return txt; }
  } catch {
    return "描述載入錯誤";
  }
}

function createCard(type, index, imageUrl) {
  const card = document.createElement("div");
  card.classList.add("select-card");
  card.dataset.type = type;
  card.dataset.index = index;

  const img = document.createElement("img");
  img.src = imageUrl;
  img.alt = `${type}-${index + 1}`;
  card.appendChild(img);

  card.onclick = () => handleSelect(card);
  return card;
}

function handleSelect(card) {
  const type = card.dataset.type;
  const index = parseInt(card.dataset.index);

  const prevSelected = imageData[type].selected;

  if (prevSelected === index) {
    imageData[type].selected = null;
    card.classList.remove("selected");
  } else {
    document.querySelectorAll(`.select-card[data-type='${type}']`)
      .forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
    imageData[type].selected = index;
    imageData[type].timestamp = Date.now();
  }

  if (type === "char") {
    const imageId = imageData.char.imageIds?.[index];
    const rawName = imageData.char.names?.[index] || "";
    const baseName = rawName.replace(/\.[^/.]+$/, "");

    if (imageId) {
      localStorage.setItem("selectedCharacterId", imageId);
      console.log("✅ 選擇角色 image_id 已儲存：", imageId);
    } else {
      console.warn("⚠️ 找不到 image_id，無法儲存");
    }

    if (baseName) {
      localStorage.setItem("selectedCharacterName", baseName);
      console.log("✅ 選擇角色名稱已儲存：", baseName);
    } else {
      console.warn("⚠️ 找不到角色名稱，無法儲存");
    }
  }

  updateCount(type);
  updateDisplay();
}

function updateDisplay() {
  displayArea.innerHTML = "";

  const charTime = imageData.char.timestamp || 0;
  const sceneTime = imageData.scene.timestamp || 0;
  const lastType = charTime > sceneTime ? "char" : "scene";
  const lastIndex = imageData[lastType].selected;
  if (lastIndex === null) return;

  const src = imageData[lastType].images[lastIndex];
  const rawName = imageData[lastType].names?.[lastIndex] || `${lastType} ${lastIndex + 1}`;
  const name = rawName.replace(/\.[^/.]+$/, "");
  const memoryDesc = lastType === "char"
    ? imageData.char.memoryDescriptions[lastIndex]
    : imageData.scene.descriptions[lastIndex];

  const shortDesc = memoryDesc.length > 100 ? memoryDesc.substring(0, 100) + "..." : memoryDesc;

  const flipContainer = document.createElement("div");
  flipContainer.className = "flip-container";
  const flipCard = document.createElement("div");
  flipCard.className = "flip-card";

  const cardFront = document.createElement("div");
  cardFront.className = "card-face card-front";
  const bg = document.createElement("img");
  bg.className = "bg-blur";
  bg.src = src;
  const fg = document.createElement("img");
  fg.className = "fg-image";
  fg.src = src;
  cardFront.appendChild(bg);
  cardFront.appendChild(fg);

  const cardBack = document.createElement("div");
  cardBack.className = "card-face card-back";
  const blur = document.createElement("div");
  blur.className = "blur-background";
  blur.style.backgroundImage = `url(${src})`;
  const content = document.createElement("div");
  content.className = "back-content";
  const title = document.createElement("h2");
  title.textContent = name;
  const desc = document.createElement("p");
  desc.textContent = shortDesc;
  content.appendChild(title);
  content.appendChild(desc);

  if (lastType === "char") {
    const moreBtn = document.createElement("button");
    moreBtn.textContent = "查看完整記憶";
    moreBtn.className = "view-more-btn";
    moreBtn.onclick = (e) => {
      e.stopPropagation();
      openDescriptionModal(memoryDesc);
    };
    content.appendChild(moreBtn);
  }

  cardBack.appendChild(blur);
  cardBack.appendChild(content);

  flipCard.appendChild(cardFront);
  flipCard.appendChild(cardBack);
  flipContainer.appendChild(flipCard);
  displayArea.appendChild(flipContainer);

  flipContainer.onclick = () => flipCard.classList.toggle("flipped");
}

function openDescriptionModal(fullText) {
  const modal = document.getElementById("descModal");
  const closeBtn = modal.querySelector(".close-btn");
  const textEl = document.getElementById("descFullText");

  textEl.textContent = fullText;
  modal.style.display = "flex";

  closeBtn.onclick = () => modal.style.display = "none";
  modal.onclick = (e) => { if (e.target === modal) modal.style.display = "none"; };
}

function updateCount(type) {
  const countEl = document.getElementById(`${type}-count`);
  const data = imageData[type];

  const total = Array.isArray(data.images) ? data.images.length : 0;

  let selected = 0;
  if (data.selected !== null && typeof data.selected === "number") {
    selected = data.selected + 1;
  }

  countEl.textContent = `${selected}/${total}`;
}

function addUploadButton() {
  const addCard = document.createElement("a");
  addCard.className = "add-card";
  addCard.textContent = "+";
  charScroll.appendChild(addCard);
  addCard.onclick = (e) => { e.preventDefault(); openInfoUploadModal(); };
}

function initSceneCards() {
  sceneScroll.innerHTML = "";
  imageData.scene.images.forEach((url, index) => {
    sceneScroll.appendChild(createCard("scene", index, url));
  });

  const addCard = document.createElement("a");
  addCard.className = "add-card";
  addCard.textContent = "+";
  sceneScroll.appendChild(addCard);
  addCard.onclick = (e) => { e.preventDefault(); showToast("目前僅開放人物上傳功能", "error"); };

  updateCount("scene");
}

loadCharacters();
initSceneCards();