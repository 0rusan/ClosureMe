# shared_memory.py
import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI  # ✅ 新版 openai 套件初始化


def _load_config(config_path: str = "config.json") -> dict:
    """
    嘗試載入 config.json。若不存在則回傳空 dict。
    支援兩種寫法：
      1) 平鋪：
         {
           "openai_api_key": "...",
           "shared_memory_base_dir": "...",
           "shared_memory_embedding_model": "...",
           "shared_memory_embedding_dim": 384
         }
      2) 區塊：
         {
           "openai_api_key": "...",
           "shared_memory": {
             "base_dir": "...",
             "embedding_model": "...",
             "embedding_dim": 384
           }
         }
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


class SharedMemoryManager:
    def __init__(
        self,
        character="default",
        config_path: str = "config.json",
        # ⬇️ 以下參數若不提供，會從 config.json 讀；若提供，優先使用參數值
        base_dir: str | None = None,
        model_name: str | None = None,
        embedding_dim: int | None = None,
        openai_key: str | None = None,
    ):
        """
        初始化規則（優先順序）：函式參數 > config.json > 預設值
        """
        cfg = _load_config(config_path)

        # 讀取 config（同時支援平鋪與嵌套結構）
        # --- OpenAI 金鑰 ---
        cfg_openai_key = cfg.get("openai_api_key") or (cfg.get("openai") or {}).get("api_key")

        # --- Shared Memory 區塊 ---
        nested = cfg.get("shared_memory") or {}
        cfg_base_dir = (
            base_dir
            or cfg.get("shared_memory_base_dir")
            or nested.get("base_dir")
            or "shared_memories"
        )
        cfg_model_name = (
            model_name
            or cfg.get("shared_memory_embedding_model")
            or nested.get("embedding_model")
            or "paraphrase-multilingual-MiniLM-L12-v2"
        )
        cfg_embedding_dim = int(
            embedding_dim
            or cfg.get("shared_memory_embedding_dim")
            or nested.get("embedding_dim")
            or 384
        )

        # 最終設定
        self.character = character
        self.embedding_dim = cfg_embedding_dim
        self.base_dir = cfg_base_dir
        self.memory_file = os.path.join(self.base_dir, f"shared_memories_{character}.txt")
        self.index_file = os.path.join(self.base_dir, f"shared_faiss_{character}.idx")
        self.openai_key = openai_key or cfg_openai_key or os.getenv("OPENAI_API_KEY")

        os.makedirs(self.base_dir, exist_ok=True)

        # 內部狀態
        self.summaries = []     # summary list
        self.full_texts = []    # detailed list
        self.index = faiss.IndexFlatL2(self.embedding_dim)

        # 向量模型
        self.model = SentenceTransformer(cfg_model_name)

        # 載入既有記憶
        if self.model:
            self._load_memories()

    # ------------------ 檔案載入/儲存 ------------------
    def _load_memories(self):
        if not os.path.exists(self.memory_file):
            print("ℹ️ 無共同記憶檔案，初始化空記憶庫")
            return

        with open(self.memory_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        for line in lines:
            if '\t' in line:
                summary, detail = line.split('\t', 1)
                self.summaries.append(summary)
                self.full_texts.append(detail)

        if self.summaries:
            embeddings = self.model.encode(
                self.summaries,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).astype('float32')
            self.index.add(embeddings)
            print(f"✅ 載入 {len(self.summaries)} 筆共同回憶")

    def add_memory(self, summary, full_text):
        if summary in self.summaries:
            print("⚠️ 該回憶已存在，略過")
            return
        self.summaries.append(summary)
        self.full_texts.append(full_text)
        embedding = self.model.encode(
            [summary], convert_to_numpy=True,
            normalize_embeddings=True
        ).astype('float32')
        self.index.add(embedding)
        with open(self.memory_file, 'a', encoding='utf-8') as f:
            f.write(f"{summary}\t{full_text}\n")
        print(f"🧠 新增共同回憶：{summary}")

    # ------------------ 檢索 ------------------
    def search_memories(self, query, k=3):
        if not self.summaries:
            return [], None, []
        embedding = self.model.encode(
            [query], convert_to_numpy=True,
            normalize_embeddings=True
        ).astype('float32')
        distances, indices = self.index.search(embedding, min(k, len(self.summaries)))
        results = [
            {"brief": self.summaries[i], "detail": self.full_texts[i], "distance": float(d)}
            for i, d in zip(indices[0], distances[0]) if i < len(self.summaries)
        ]
        return results, embedding, distances[0]

    # ------------------ 自動摘要（透過 OpenAI） ------------------
    def auto_extract_shared_memory(self, user_input, ai_response, openai_api_key=None):
        """
        使用 OpenAI 產生「簡要摘要 / 詳細內容」，成功後自動寫入記憶檔。
        金鑰優先順序：傳入參數 > config.json > 環境變數 OPENAI_API_KEY
        """
        key = openai_api_key or self.openai_key or os.getenv("OPENAI_API_KEY")
        if not key:
            print("❌ 找不到可用的 OpenAI API 金鑰")
            return None, None

        client = OpenAI(api_key=key)

        prompt = f"""你是一個總結助手。請將以下對話內容整理成一段「共同回憶摘要」，以供AI記錄。輸出格式如下：
簡要摘要：xxx
詳細內容：yyy

對話如下：
使用者說：「{user_input}」
AI 回覆：「{ai_response}」

請輸出結果："""

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.choices[0].message.content.strip()
            summary, detail = "", ""
            for line in text.splitlines():
                if "簡要摘要" in line:
                    summary = line.split("：", 1)[-1].strip()
                elif "詳細內容" in line:
                    detail = line.split("：", 1)[-1].strip()
            if summary and detail:
                self.add_memory(summary, detail)
                return summary, detail
        except Exception as e:
            print("❌ 自動提取回憶失敗：", e)
        return None, None
