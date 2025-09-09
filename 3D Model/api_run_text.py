# -*- coding: utf-8 -*-
# api_run_text.py（純本機版：固定打 http://127.0.0.1:8080/generate）
import base64
import json
import requests
import os
from PIL import Image, UnidentifiedImageError
from glob import glob

# 直接固定：本機 Hunyuan3D 服務
API_URL = "http://127.0.0.1:8080/generate"

# 固定輸出：OBJ + 含材質
OUTPUT_FORMAT = "obj"
WITH_TEXTURE = True

def find_project_root() -> str | None:
    cand = []
    env_root = os.environ.get("HY3D_ROOT")
    if env_root:
        cand.append(env_root)

    here = os.path.dirname(os.path.abspath(__file__))
    cwd  = os.getcwd()
    home = os.path.expanduser("~")

    cand += [
        here,
        os.path.dirname(here),
        cwd,
        os.path.join(here, "Hunyuan3D-2"),
        os.path.join(cwd,  "Hunyuan3D-2"),
        os.path.join(home, "Hunyuan3D-2"),
    ]

    seen = set()
    for root in cand:
        root = os.path.abspath(root)
        if root in seen:
            continue
        seen.add(root)
        if os.path.isdir(os.path.join(root, "demo", "images")):
            return root
    return None

def main():
    project_root = find_project_root()
    if not project_root:
        print("❌ 找不到專案根目錄（需包含 demo/images）。可：")
        print("  1) 把這個腳本放在 Hunyuan3D-2 專案內或其父資料夾，或")
        print("  2) 設定環境變數 HY3D_ROOT 指向 Hunyuan3D-2，例如：")
        print(r"     set HY3D_ROOT=C:\Users\B310\Hunyuan3D-2")
        return

    image_dir = os.path.join(project_root, "demo", "images")
    base_output_dir = os.path.join(project_root, "demo", "output")
    os.makedirs(base_output_dir, exist_ok=True)

    # 準備輸出資料夾（001, 002, ...）
    existing = [int(d) for d in os.listdir(base_output_dir)
                if d.isdigit() and os.path.isdir(os.path.join(base_output_dir, d))]
    next_id = (max(existing) + 1) if existing else 1
    folder_name = f"{next_id:03d}"
    output_dir = os.path.join(base_output_dir, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    # 收集所有圖片
    img_paths = sorted(
        glob(os.path.join(image_dir, "*.jpg")) +
        glob(os.path.join(image_dir, "*.jpeg")) +
        glob(os.path.join(image_dir, "*.png")) +
        glob(os.path.join(image_dir, "*.webp")) +
        glob(os.path.join(image_dir, "*.bmp"))
    )
    if not img_paths:
        print(f"⚠️ 找不到任何圖片。請把 .jpg/.png 放到：{image_dir}")
        return

    print(f"📦 本次輸出資料夾：{output_dir}")
    print(f"🧩 固定輸出格式：{OUTPUT_FORMAT}（含材質：{WITH_TEXTURE}）")
    print(f"🔗 本機生成端點：{API_URL}")

    # 批次處理
    for idx, img_path in enumerate(img_paths, start=1):
        stem = f"{idx:03d}"
        filename = f"{stem}.{OUTPUT_FORMAT}"
        out_path = os.path.join(output_dir, filename)

        # 檢查圖片
        try:
            Image.open(img_path).close()
        except UnidentifiedImageError:
            print(f"❌ 圖片格式不支援：{img_path}，跳過")
            continue
        except Exception as e:
            print(f"❌ 圖片 {img_path} 無法開啟（{e}），跳過")
            continue

        # 轉 base64（本機通常不需壓縮；若仍遇到 413 再說）
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        print(f"\n🖼️ 處理圖片 {img_path} ➜ {out_path}")

        payload = {
            "image": img_b64,
            "type": OUTPUT_FORMAT,
            "name": folder_name,     # 後端會存到 demo/output/<name>/
            "filename": filename,    # 後端就用這個檔名存
            "with_texture": WITH_TEXTURE,
        }

        try:
            resp = requests.post(
                API_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=600,
            )
        except requests.exceptions.RequestException as e:
            print("❌ 無法連線到本機生成服務：", e)
            return

        if resp.status_code == 200:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            print(f"✅ 已儲存為：{out_path}")
        else:
            print(f"❌ 生成服務錯誤（{resp.status_code}）：{img_path}")
            try:
                print("回應：", resp.json())
            except Exception:
                print("回應：", resp.text)
            # 若本機服務回錯，直接結束本輪，避免後續組裝找不到檔案
            return

if __name__ == "__main__":
    main()

