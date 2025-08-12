from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, session
import os
import json
import re
import openai
from openai import OpenAI
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "upload_key"
UPLOAD_FOLDER = "uploads"
ROLE_FOLDER = "roles"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ROLE_FOLDER, exist_ok=True)

openai.api_key = "please-input-your-api-key"  # ✅ 建議使用環境變數
client = OpenAI(api_key=openai.api_key)

def extract_speaker_names(text):
    lines = text.strip().splitlines()
    speakers = set()
    for line in lines:
        if re.match(r"\d{2}:\d{2}\s+(\S+)", line):
            match = re.match(r"\d{2}:\d{2}\s+(\S+)", line)
            if match:
                speakers.add(match.group(1))
    return sorted(speakers)

def extract_speaker_lines(text, target_name):
    lines = text.strip().splitlines()
    filtered = []
    for line in lines:
        match = re.match(r"^(\d{2}:\d{2})\s+(\S+)\s+(.*)$", line)
        if match:
            _, speaker, content = match.groups()
            if speaker == target_name:
                if content and not re.match(r"(圖片|貼圖|影片|未接來電|取消)", content):
                    filtered.append(content.strip())
    return filtered


def ask_openai_to_generate_prompt(name, messages):
    sample_dialogue = "\n".join(f"- {m}" for m in messages[:30])

    system_prompt = f"""
你是一個語言風格分析專家，請根據 LINE 聊天中角色「{name}」的發言內容，產出一段適合用來模仿此角色的 prompt。

🧠 分析要點：
1. 角色與使用者的關係（如：家人、朋友）
2. 語氣特徵（如：溫柔、口語化、碎念、有禮貌、冷靜）
3. 講話方式（是否簡短、直接、會不會碎碎念）
4. 語助詞與慣用語氣（如：啦、喔、啊、嘿）
5. 回應習慣（句數是否簡短、語句是否完整）
6. 在角色風格描述的句尾加上(如果你輸出的字數超過 20 字，請自動縮減為最自然的版本。)

🚫 禁止事項：
- 不要複製對話原句當作示範
- 不要出現「例如」「他常說」
- 不要用 overly positive（太正面）或書面語風格
- 不要給多段 JSON，只能回傳一段標準格式

✅ 請只輸出以下 JSON 格式（不要有解釋）：
{{
  "name": "{name}",
  "prompt": "（一段可用於 AI 模仿該角色的說話風格之描述）"
}}

📄 以下是角色「{name}」的 LINE 對話樣本（僅供參考，不要複製）：
{sample_dialogue}
"""
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": system_prompt.strip()}]
    )
    return response.choices[0].message.content.strip()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["chat_file"]
        if file.filename == "":
            return "❌ 請上傳檔案。"

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        speaker_names = extract_speaker_names(raw_text)
        session["chat_file"] = filepath
        session["speaker_names"] = speaker_names
        return render_template_string(SPEAKER_SELECTION_HTML, speakers=speaker_names)

    return render_template_string(UPLOAD_FORM_HTML)

@app.route("/generate", methods=["POST"])
def generate():
    role_name = request.form["selected_speaker"]
    filepath = session.get("chat_file")

    if not filepath or not os.path.exists(filepath):
        return "❌ 找不到聊天記錄檔案，請重新上傳"

    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    messages = extract_speaker_lines(raw_text, role_name)
    if not messages:
        return "⚠️ 找不到角色發言訊息"

    result = ask_openai_to_generate_prompt(role_name, messages)

    try:
        data = json.loads(result)
        filename = f"{role_name}.json"
        path = os.path.join(ROLE_FOLDER, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return redirect(url_for("download_file", filename=filename))
    except json.JSONDecodeError:
        return f"❌ 無法解析 OpenAI 回傳內容：<br><pre>{result}</pre>"

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(ROLE_FOLDER, filename, as_attachment=True)

# -------------------- HTML Templates --------------------
UPLOAD_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>角色模仿提示詞產生器</title></head>
<body style="font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto;">
    <h2>📂 上傳聊天檔案 ➜ 擷取講話者</h2>
    <form method="POST" enctype="multipart/form-data">
        <label>選擇聊天 .txt 檔案：</label><br>
        <input type="file" name="chat_file" required><br><br>
        <button type="submit">➡️ 下一步</button>
    </form>
</body>
</html>
"""

SPEAKER_SELECTION_HTML = """
<!DOCTYPE html>
<html>
<head><title>選擇講話者</title></head>
<body style="font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto;">
    <h2>🗣️ 從檔案中找到這些講話者：</h2>
    <form method="POST" action="/generate">
        <label>選擇要模仿的角色：</label><br>
        <select name="selected_speaker" required>
            {% for s in speakers %}
            <option value="{{ s }}">{{ s }}</option>
            {% endfor %}
        </select><br><br>
        <button type="submit">🎯 產生角色提示詞</button>
    </form>
</body>
</html>
"""

# -------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True,port=5001)
