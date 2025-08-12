from flask import Flask, render_template_string, request, redirect
import pickle
import os

app = Flask(__name__)
STRUCTURED_MEMORY_FILE = "structured_memories.pkl"

# 預設格式化記憶結構
default_memory = {
    "名字": "",
    "興趣": set(),
    "喜好": set(),
    "厭惡": set(),
    "生日": ""
}

# 載入格式化記憶
def load_structured_memory():
    if os.path.exists(STRUCTURED_MEMORY_FILE):
        with open(STRUCTURED_MEMORY_FILE, "rb") as f:
            memory = pickle.load(f)
            for key in ["興趣", "喜好", "厭惡"]:
                if not isinstance(memory.get(key, None), set):
                    memory[key] = set()
            return memory
    return default_memory.copy()

# 儲存格式化記憶
def save_structured_memory(memory):
    with open(STRUCTURED_MEMORY_FILE, "wb") as f:
        pickle.dump(memory, f)

# 主介面
@app.route("/", methods=["GET", "POST"])
def edit_memory():
    if request.method == "POST":
        memory = {
            "名字": request.form["名字"].strip(),
            "生日": request.form["生日"].strip(),
            "興趣": set(x.strip() for x in request.form["興趣"].split("、") if x.strip()),
            "喜好": set(x.strip() for x in request.form["喜好"].split("、") if x.strip()),
            "厭惡": set(x.strip() for x in request.form["厭惡"].split("、") if x.strip())
        }
        save_structured_memory(memory)
        return redirect("/")

    memory = load_structured_memory()
    return render_template_string("""
    <!DOCTYPE html>
    <html><body style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <h2>🧠 編輯格式化記憶</h2>
        <form method="post">
            <label>名字：</label><br>
            <input type="text" name="名字" value="{{ memory['名字'] }}"><br><br>

            <label>生日：</label><br>
            <input type="text" name="生日" value="{{ memory['生日'] }}"><br><br>

            <label>興趣（以「、」分隔）：</label><br>
            <input type="text" name="興趣" value="{{ '、'.join(memory['興趣']) }}"><br><br>

            <label>喜好（以「、」分隔）：</label><br>
            <input type="text" name="喜好" value="{{ '、'.join(memory['喜好']) }}"><br><br>

            <label>厭惡（以「、」分隔）：</label><br>
            <input type="text" name="厭惡" value="{{ '、'.join(memory['厭惡']) }}"><br><br>

            <button type="submit">💾 儲存變更</button>
        </form>
    </body></html>
    """, memory=memory)

if __name__ == "__main__":
    app.run(debug=True, port=5002)  # ✅ 你可以改為其他 port，例如 5010
