from flask import Flask, request, jsonify, render_template_string, redirect
import openai
import os, json
from datetime import datetime

from memory_sup_API import MemoryManager
from shared_memory import SharedMemoryManager  # ✅ 強化版（建議支援 openai_key 參數）

# -------------------- 讀取設定 --------------------
DEFAULT_CONFIG = {
    "openai_api_key": "please-input-your-api-key",
    "model_name": "gpt-4.1-nano",
    "distance_threshold": 1.15,
    "preference_distance_threshold": 1.03,
    "trigger_keywords": ["回憶", "記得嗎", "你還記得", "上次說到", "關於那件", "提醒我", "之前", "名字", "愛", "喜歡", "討厭"]
}
CONFIG_PATH = "config.json"

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = {**DEFAULT_CONFIG, **json.load(f)}
else:
    cfg = DEFAULT_CONFIG

OPENAI_API_KEY = cfg.get("openai_api_key") or os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = cfg.get("model_name", DEFAULT_CONFIG["model_name"])
DISTANCE_THRESHOLD = float(cfg.get("distance_threshold", DEFAULT_CONFIG["distance_threshold"]))
PREFERENCE_DISTANCE_THRESHOLD = float(cfg.get("preference_distance_threshold", DEFAULT_CONFIG["preference_distance_threshold"]))
TRIGGER_KEYWORDS = cfg.get("trigger_keywords", DEFAULT_CONFIG["trigger_keywords"])

# -------------------- Flask 初始化 --------------------
app = Flask(__name__)

# ✅ 建議改用環境變數；這裡仍支援 config.json
openai.api_key = OPENAI_API_KEY

# -------------------- 記憶系統初始化 --------------------
memory_manager = MemoryManager(
    embedding_dim=384,
    index_file="chat_faiss.idx",
    memories_pickle_file="chat_text_memories.pkl",
    persistent_text_file="persistent_memories.txt"
)

history = []
current_role = "default"
# ✅ 若你的 SharedMemoryManager 支援 openai_key，這裡一併傳入
shared_memory_manager = SharedMemoryManager(character=current_role, embedding_dim=384, openai_key=OPENAI_API_KEY)

# -------------------- 小工具 --------------------
def should_retrieve_memory(text: str) -> bool:
    return any(keyword in text for keyword in TRIGGER_KEYWORDS)

def load_role_prompt(role_name: str):
    path = f"roles/{role_name.lower()}.json"
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("prompt", "")

def log_auto_shared_memory(summary, detail, user_input, reply):
    os.makedirs("logs", exist_ok=True)
    with open("logs/shared_memory_add.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 新增共同記憶]\n")
        f.write(f"簡要摘要：{summary}\n詳細內容：{detail}\n使用者說：{user_input}\nAI 回覆：{reply}\n{'='*40}\n")

# -------------------- 首頁 UI --------------------
@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI 對話機器人</title>
        <style>
            body { font-family: sans-serif; padding: 20px; max-width: 720px; margin: auto; }
            .topbar { display:flex; justify-content: space-between; align-items:center; margin-bottom:10px; }
            .chat-box { border: 1px solid #ccc; padding: 10px; height: 420px; overflow-y: scroll; }
            .actions a { text-decoration:none; padding:6px 10px; border:1px solid #999; border-radius:6px; margin-left:8px; }
            input { width: 100%; padding: 10px; }
            .cfg { color:#666; font-size: 12px; margin-bottom:6px; }
        </style>
    </head>
    <body>
        <div class="topbar">
            <h2>🧠 AI 對話機器人</h2>
            <div class="actions">
                <a href="/memory" target="_blank">⚙️ 編輯格式化記憶</a>
                <a href="/config" target="_blank">🛠️ 查看設定</a>
            </div>
        </div>
        <div class="cfg">模型：{{model}}　一般檢索門檻：{{dist}}　偏好檢索門檻：{{pdist}}</div>
        <div class="chat-box" id="chat-box"></div>
        <input type="text" id="input" placeholder="輸入訊息並按 Enter，例如 /use 鄒順美 或 /end" autofocus />
        <script>
            const box = document.getElementById('chat-box');
            const input = document.getElementById('input');
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    const msg = input.value.trim();
                    if (!msg) return;
                    box.innerHTML += "<b>你：</b>" + msg + "<br>";
                    input.value = "";
                    fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: msg })
                    })
                    .then(r => r.json())
                    .then(data => {
                        box.innerHTML += "<b>AI：</b>" + (data.reply || "(無回覆)") + "<br>";
                        if (data.shared_memory_added) {
                            box.innerHTML += "<i>📌 已新增共同回憶：「" + data.shared_memory_added.summary + "」</i><br>";
                        }
                        box.scrollTop = box.scrollHeight;
                    })
                    .catch(err => {
                        box.innerHTML += "<span style='color:#b00'>❌ 錯誤：" + err + "</span><br>";
                    });
                }
            });
        </script>
    </body>
    </html>
    """, model=MODEL_NAME, dist=DISTANCE_THRESHOLD, pdist=PREFERENCE_DISTANCE_THRESHOLD)

# -------------------- 查看設定（只讀） --------------------
@app.route('/config')
def view_config():
    safe_cfg = dict(cfg)
    if "openai_api_key" in safe_cfg and safe_cfg["openai_api_key"]:
        safe_cfg["openai_api_key"] = safe_cfg["openai_api_key"][:8] + "•••(hidden)"
    return jsonify(safe_cfg)

# -------------------- 對話 API --------------------
@app.route('/chat', methods=['POST'])
def chat():
    global history, current_role, shared_memory_manager
    user_input = request.json.get("message", "")

    # /end 重置
    if user_input.strip().lower() == "/end":
        history = []
        current_role = "default"
        shared_memory_manager = SharedMemoryManager(character="default", embedding_dim=384, openai_key=OPENAI_API_KEY)
        return jsonify({"reply": "🧹 對話已結束，角色與歷史記錄已清除。"})

    # /use 切換角色
    if user_input.lower().startswith("/use "):
        role_name = user_input[5:].strip()
        prompt = load_role_prompt(role_name)
        if prompt:
            current_role = role_name
            history = [{"role": "system", "content": prompt}]
            shared_memory_manager = SharedMemoryManager(character=current_role, embedding_dim=384, openai_key=OPENAI_API_KEY)
            return jsonify({"reply": f"🧑‍🎤 已切換為角色：{role_name}"})
        else:
            return jsonify({"reply": f"❌ 無法找到角色 `{role_name}`"})

    # 1) 從自然語句中擷取結構化記憶（會自動更新偏好索引）
    memory_manager.update_structured_memory(user_input)

    # 2) 只給固定背景：名字
    personal_info = memory_manager.get_structured_memory_prompt(fixed_fields={"名字"})

    # 3) 一般語意記憶檢索（長文）
    retrieved_text = ""
    if memory_manager.get_total_memories() > 0 and should_retrieve_memory(user_input):
        mems, vec, dists = memory_manager.search_memories(user_input, k=5)
        relevant = [m for m, d in zip(mems, dists) if d < DISTANCE_THRESHOLD]
        if relevant:
            retrieved_text = "以下是我記錄的相關資訊：\n" + "\n".join(f"- {x}" for x in relevant) + "\n"

    # 4) 偏好/興趣/厭惡/生日（向量檢索，語意相近才注入）
    preference_text = ""
    if should_retrieve_memory(user_input):
        pref_hits = memory_manager.search_preferences(
            user_input,
            k=5,
            distance_threshold=PREFERENCE_DISTANCE_THRESHOLD,
            types={"喜好", "厭惡", "興趣", "生日"}
        )
        if pref_hits:
            lines = []
            for h in pref_hits[:3]:
                label = {"喜好":"喜好", "厭惡":"厭惡", "興趣":"興趣", "生日":"生日"}[h["type"]]
                lines.append(f"- 可能相關的{label}：{h['text']}")
            preference_text = "以下是可能相關的個人偏好（語意比對）：\n" + "\n".join(lines) + "\n"

    # 5) 共同回憶檢索
    shared_text = ""
    shared_used = []
    shared_results, _, _ = shared_memory_manager.search_memories(user_input, k=3)
    for item in shared_results:
        brief = item["brief"]
        detail = item["detail"]
        dist = item["distance"]
        shared_text += f"- {brief}\n"
        shared_used.append({"brief": brief, "detail": detail, "distance": round(float(dist), 4)})

    if shared_text:
        shared_text = "這是我們共同經歷的回憶：\n" + shared_text

    # 6) 組合 Prompt 並呼叫模型
    full_prompt = personal_info + retrieved_text + preference_text + shared_text + user_input
    try:
        response = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=history + [{"role": "user", "content": full_prompt}]
        )
        reply = response.choices[0].message.content
    except Exception as e:
        return jsonify({"reply": f"❌ 錯誤：{str(e)}"})

    # 7) 保存歷史
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply})

    # 8) 自動新增共同回憶（若命中觸發詞）
    shared_memory_added = None
    if should_retrieve_memory(user_input):
        summary, detail = shared_memory_manager.auto_extract_shared_memory(
            user_input, reply, openai_api_key=OPENAI_API_KEY)
        if summary and detail:
            shared_memory_manager.add_memory(summary, detail)
            shared_memory_added = {"summary": summary, "detail": detail}
            log_auto_shared_memory(summary, detail, user_input, reply)

    return jsonify({
        "reply": reply,
        "shared_memories_used": shared_used,
        "shared_memory_added": shared_memory_added
    })

# -------------------- 格式化記憶編輯 UI --------------------
@app.route('/memory', methods=['GET', 'POST'])
def memory_editor():
    m = memory_manager.structured_memory

    if request.method == 'POST':
        m["名字"] = request.form.get("名字", "").strip() or None
        m["生日"] = request.form.get("生日", "").strip() or None

        def to_set(field):
            raw = request.form.get(field, "")
            parts = [p.strip() for p in raw.replace(",", "、").split("、") if p.strip()]
            return set(parts)

        m["興趣"] = to_set("興趣")
        m["喜好"] = to_set("喜好")
        m["厭惡"] = to_set("厭惡")

        try:
            import pickle
            with open(memory_manager.structured_memory_file, "wb") as f:
                pickle.dump(m, f)
            # ✅ 立刻重建偏好索引
            memory_manager._rebuild_preferences_index()
        except Exception as e:
            return f"❌ 儲存失敗：{e}"

        return redirect('/memory')

    def join_set(s):
        return "、".join(sorted(s)) if isinstance(s, set) else (s or "")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚙️ 格式化記憶管理</title>
        <style>
            body {{ font-family: sans-serif; max-width: 720px; margin: auto; padding: 20px; }}
            .row {{ margin-bottom: 14px; }}
            label {{ display:block; font-weight:600; margin-bottom:6px; }}
            input {{ width:100%; padding:8px; }}
            .tips {{ color:#666; font-size:12px; }}
            .toolbar a {{ text-decoration:none; padding:6px 10px; border:1px solid #999; border-radius:6px; margin-right:8px; }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <a href="/">← 返回聊天</a>
        </div>
        <h2>⚙️ 個人格式化記憶管理</h2>
        <form method="POST">
            <div class="row">
                <label>名字</label>
                <input name="名字" value="{m.get('名字') or ''}">
            </div>
            <div class="row">
                <label>生日</label>
                <input name="生日" value="{m.get('生日') or ''}">
            </div>
            <div class="row">
                <label>興趣</label>
                <input name="興趣" value="{join_set(m.get('興趣', set()))}">
                <div class="tips">以「、」或逗號分隔多個項目</div>
            </div>
            <div class="row">
                <label>喜好</label>
                <input name="喜好" value="{join_set(m.get('喜好', set()))}">
                <div class="tips">以「、」或逗號分隔多個項目</div>
            </div>
            <div class="row">
                <label>厭惡</label>
                <input name="厭惡" value="{join_set(m.get('厭惡', set()))}">
                <div class="tips">以「、」或逗號分隔多個項目</div>
            </div>
            <button type="submit">💾 儲存變更</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(html)

# -------------------- 入口 --------------------
if __name__ == "__main__":
    app.run(debug=True)
