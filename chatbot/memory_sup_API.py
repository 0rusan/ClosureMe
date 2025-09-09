# memory_sup_API.py
import faiss
import numpy as np
import os
import pickle
import torch
from sentence_transformers import SentenceTransformer
import re
import json

# -------------------- 讀取設定檔 --------------------
CONFIG_PATH = "config.json"
DEFAULT_CFG = {
    # 向量模型/維度
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "embedding_dim": 384,

    # 檔案路徑
    "text_index_file": "chat_faiss.idx",
    "text_memories_pickle": "chat_text_memories.pkl",
    "text_memories_persistent": "persistent_memories.txt",
    "structured_memory_file": "structured_memories.pkl",

    # 偏好檢索預設門檻（可被 search_preferences 呼叫時覆寫）
    "preference_distance_threshold": 1.03
}

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CFG = {**DEFAULT_CFG, **json.load(f)}
else:
    CFG = DEFAULT_CFG


def format_vector_snippet(vector, n=5):
    if not isinstance(vector, np.ndarray):
        vector = np.array(vector)
    if vector.ndim > 1:
        vector = vector.flatten()
    if vector.size == 0:
        return "[]"
    if vector.size <= 2 * n:
        return f"{vector.tolist()}"
    first_part = [f"{x:.4f}" for x in vector[:n]]
    last_part = [f"{x:.4f}" for x in vector[-n:]]
    return f"[{', '.join(first_part)}, ..., {', '.join(last_part)}]"


class MemoryManager:
    def __init__(self,
                 model_name=None,
                 embedding_dim=None,
                 index_file=None,
                 memories_pickle_file=None,
                 persistent_text_file=None,
                 structured_memory_file=None,
                 embedding_fn=None):
        """
        參數留空時會讀取 config.json：
          - model_name → CFG["embedding_model"]
          - embedding_dim → CFG["embedding_dim"]
          - index_file → CFG["text_index_file"]
          - memories_pickle_file → CFG["text_memories_pickle"]
          - persistent_text_file → CFG["text_memories_persistent"]
          - structured_memory_file → CFG["structured_memory_file"]
        """
        # ---- 套用設定檔或覆寫值
        self.embedding_dim = int(embedding_dim or CFG["embedding_dim"])
        self.index_file = index_file or CFG["text_index_file"]
        self.memories_pickle_file = memories_pickle_file or CFG["text_memories_pickle"]
        self.persistent_text_memories_file = persistent_text_file or CFG["text_memories_persistent"]
        self.structured_memory_file = structured_memory_file or CFG["structured_memory_file"]
        model_name = model_name or CFG["embedding_model"]

        # 偏好檢索門檻（預設值，可在 search_preferences 呼叫時覆寫）
        self.default_pref_threshold = float(CFG.get("preference_distance_threshold", 1.03))

        print("🚀 初始化記憶管理器 (讀取 config.json)...")
        print(f"• model_name={model_name}")
        print(f"• embedding_dim={self.embedding_dim}")
        print(f"• index_file={self.index_file}")
        print(f"• memories_pickle_file={self.memories_pickle_file}")
        print(f"• persistent_text_memories_file={self.persistent_text_memories_file}")
        print(f"• structured_memory_file={self.structured_memory_file}")

        # ✅ 結構化記憶：僅「名字」固定輸出；其餘走向量檢索
        self.structured_memory = {
            "名字": None,
            "興趣": set(),
            "喜好": set(),
            "厭惡": set(),
            "生日": None
        }

        # 嵌入模型
        if embedding_fn is None:
            try:
                self.embed_model = SentenceTransformer(model_name)
                if torch.cuda.is_available():
                    self.embed_model = self.embed_model.to(torch.device("cuda"))
                print(f"✅ 嵌入模型 '{model_name}' 載入成功。")
            except Exception as e:
                print(f"❌ 嵌入模型載入失敗: {e}")
                raise
        else:
            print("✅ 使用外部提供的 embedding function（例如 OpenAI Embedding API）")
            self.embedding_fn = embedding_fn

        # 一般文字記憶（語意檢索）
        self.text_memories = []
        self.index = faiss.IndexFlatL2(self.embedding_dim)

        self._load_or_rebuild_from_persistent_file()
        self._load_structured_memories()

        # ✅ 偏好索引（興趣/喜好/厭惡/生日）
        self._init_preference_index()

    # ------------------ 結構化記憶 ------------------
    def _load_structured_memories(self):
        if os.path.exists(self.structured_memory_file):
            try:
                with open(self.structured_memory_file, 'rb') as f:
                    self.structured_memory = pickle.load(f)
                # 保證集合型別
                for k in ["興趣", "喜好", "厭惡"]:
                    if not isinstance(self.structured_memory.get(k), set):
                        self.structured_memory[k] = set(self.structured_memory.get(k) or [])
                print(f"✅ 已載入格式化記憶：{self.structured_memory}")
            except Exception as e:
                print(f"⚠️ 無法讀取格式化記憶: {e}")

    def update_structured_memory(self, text):
        patterns = {
            "名字": r"(?:我叫|我的名字是)([\u4e00-\u9fa5A-Za-z·．\s]{2,15})",
            "興趣": r"(?:我的興趣是|我(的)?興趣包括|我喜歡.*?的活動是)([^。,\s]{2,15})",
            "喜好": r"(?:我喜歡|我很喜歡)([^。,\s]{2,15})",
            "厭惡": r"(?:我討厭|我不喜歡)([^。,\s]{2,15})",
            "生日": r"我的生日是(\d{1,2}[月/-]\d{1,2}[日]?)"
        }
        blacklist = {"的", "的東西", "啦", "喔", "嗯", "東西", "那個", "這個", "吧", "耶", "啦啦", "XDD", "XD", "哈哈"}

        updated = False
        updated_pref = False

        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if len(value) < 2 or value in blacklist:
                    print(f"⚠️ 擷取結果過短或在黑名單中，略過：{value}")
                    continue

                if key in ["名字", "生日"]:
                    self.structured_memory[key] = value
                    print(f"🧾 格式化記憶更新: {key} ➜ {value}")
                    if key == "生日":
                        updated_pref = True
                else:
                    if key not in self.structured_memory or not isinstance(self.structured_memory[key], set):
                        self.structured_memory[key] = set()
                    self.structured_memory[key].add(value)
                    print(f"🧾 格式化記憶更新: {key} ➜ {value}")
                    updated_pref = True

                updated = True
                break  # 每次僅更新一筆

        if updated:
            print(f"📌 偵測到格式化記憶：{self.structured_memory}")
            # 落盤
            try:
                with open(self.structured_memory_file, 'wb') as f:
                    pickle.dump(self.structured_memory, f)
            except Exception as e:
                print(f"⚠️ 儲存格式化記憶失敗：{e}")

            # 若偏好相關有更新，重建偏好索引
            if updated_pref:
                self._rebuild_preferences_index()

    def get_structured_memory_prompt(self, fixed_fields=None):
        """
        ✅ 只輸出固定背景（預設為名字）。其餘欄位改由語意觸發檢索。
        fixed_fields: 想固定輸出的欄位集合，預設僅 {"名字"}
        """
        if fixed_fields is None:
            fixed_fields = {"名字"}
        lines = []
        for field in fixed_fields:
            val = self.structured_memory.get(field)
            if isinstance(val, set):
                if val:
                    lines.append(f"- {field}：{', '.join(sorted(val))}")
            elif val:
                lines.append(f"- {field}：{val}")
        return "以下是我已知的使用者基本資訊：\n" + "\n".join(lines) + "\n" if lines else ""

    # ------------------ 一般文字記憶（語意檢索） ------------------
    def _load_or_rebuild_from_persistent_file(self):
        self.index.reset()
        self.text_memories = []

        if not os.path.exists(self.persistent_text_memories_file):
            print(f"ℹ️ 持久記憶檔案 '{self.persistent_text_memories_file}' 不存在。將以空記憶啟動。")
            self._save_faiss_and_pkl()
            return

        print(f"🔄 從 '{self.persistent_text_memories_file}' 完整重建記憶...")
        loaded_memories = []
        try:
            with open(self.persistent_text_memories_file, 'r', encoding='utf-8') as f:
                for line in f:
                    mem_text = line.strip()
                    if mem_text:
                        loaded_memories.append(mem_text)

            unique_memories = list(dict.fromkeys(loaded_memories))
            for mem_text in unique_memories:
                self._add_text_to_internal_stores(mem_text, verbose=False)

            self._save_faiss_and_pkl()
            print(f"✅ 成功載入 {len(self.text_memories)} 條記憶。")
        except Exception as e:
            print(f"❌ 載入記憶時錯誤: {e}。將以空記憶啟動。")
            self.index.reset()
            self.text_memories = []
            self._save_faiss_and_pkl()

    def _add_text_to_internal_stores(self, text_to_remember, verbose=True):
        if not text_to_remember.strip() or text_to_remember in self.text_memories:
            return False
        try:
            if hasattr(self, 'embedding_fn') and self.embedding_fn:
                embedding = np.array([self.embedding_fn(text_to_remember)], dtype=np.float32)
            else:
                embedding = self.embed_model.encode([text_to_remember], convert_to_numpy=True, normalize_embeddings=True)
                embedding = embedding.astype('float32')

            if embedding.shape[1] != self.embedding_dim:
                print(f"❌ 嵌入維度錯誤 for '{text_to_remember[:30]}...'")
                return False

            if verbose:
                print(f"   向量化 \"{text_to_remember[:30]}...\" (維度: {embedding.shape}): {format_vector_snippet(embedding)}")

            self.index.add(embedding)
            self.text_memories.append(text_to_remember)
            return True
        except Exception as e:
            print(f"❌ 新增記憶時出錯: {e}")
            return False

    def add_memory(self, text_to_remember):
        if not text_to_remember.strip():
            print("⚠️ 空白記憶，已忽略。")
            return
        if text_to_remember in self.text_memories:
            print(f"ℹ️ 記憶已存在: \"{text_to_remember[:50]}...\"")
            return

        print(f"🧠 新記憶嵌入: \"{text_to_remember[:50]}...\"")
        if self._add_text_to_internal_stores(text_to_remember, verbose=True):
            try:
                with open(self.persistent_text_memories_file, 'a', encoding='utf-8') as f:
                    f.write(text_to_remember + "\n")
                print(f"📝 已儲存至 '{self.persistent_text_memories_file}'")
                self._save_faiss_and_pkl()
                print(f"✅ 新增成功，共 {self.index.ntotal} 條記憶。")
            except Exception as e:
                print(f"❌ 儲存記憶時錯誤: {e}")
        else:
            print(f"⚠️ 記憶未儲存: \"{text_to_remember[:50]}...\"")

    def _save_faiss_and_pkl(self):
        try:
            if self.index.ntotal == len(self.text_memories):
                faiss.write_index(self.index, self.index_file)
                with open(self.memories_pickle_file, 'wb') as f:
                    pickle.dump(self.text_memories, f)
            else:
                print(f"⚠️ FAISS 與文字記憶數量不符，未儲存。")
        except Exception as e:
            print(f"❌ 儲存錯誤: {e}")

    def save_memories_on_exit(self):
        print("💾 儲存離開前狀態...")
        self._save_faiss_and_pkl()
        with open(self.structured_memory_file, 'wb') as f:
            pickle.dump(self.structured_memory, f)
        print(f"✅ 共儲存 {self.index.ntotal} 條記憶。格式化記憶欄位 {len(self.structured_memory)} 項。")

    def search_memories(self, query_text, k=3):
        if not query_text.strip() or self.index.ntotal == 0:
            return [], None, []
        try:
            if hasattr(self, 'embedding_fn') and self.embedding_fn:
                query_embedding = np.array([self.embedding_fn(query_text)], dtype=np.float32)
            else:
                query_embedding = self.embed_model.encode([query_text], convert_to_numpy=True, normalize_embeddings=True)
                query_embedding = query_embedding.astype('float32')

            if query_embedding.shape[1] != self.embedding_dim:
                print(f"❌ 查詢嵌入維度不符。")
                return [], None, []

            actual_k = min(k, self.index.ntotal)
            distances, indices = self.index.search(query_embedding, actual_k)
            retrieved_texts = [self.text_memories[i] for i in indices[0]]
            return retrieved_texts, query_embedding, distances[0]
        except Exception as e:
            print(f"❌ 搜尋記憶錯誤: {e}")
            return [], None, []

    def get_total_memories(self):
        return self.index.ntotal

    def reload_external_memories(self):
        print(f"🔄 重新載入 '{self.persistent_text_memories_file}'...")
        self._load_or_rebuild_from_persistent_file()
        self._load_structured_memories()
        self._rebuild_preferences_index()

    # ------------------ 偏好索引（興趣/喜好/厭惡/生日） ------------------
    def _init_preference_index(self):
        self.pref_index = faiss.IndexFlatL2(self.embedding_dim)
        self.pref_items = []  # list of {"type":類別, "text":值, "surface":檢索句}
        self._rebuild_preferences_index()

    def _rebuild_preferences_index(self):
        self.pref_index.reset()
        self.pref_items = []

        def add_items(t):
            vals = self.structured_memory.get(t)
            if t == "生日":
                if vals:
                    self.pref_items.append({"type": "生日", "text": vals, "surface": f"我的生日是{vals}"})
            elif isinstance(vals, set):
                for v in sorted(vals):
                    v = v.strip()
                    if not v:
                        continue
                    if t == "喜好":
                        surface = f"我喜歡{v}"
                    elif t == "厭惡":
                        surface = f"我不喜歡{v}"
                    else:  # 興趣
                        surface = f"我的興趣是{v}"
                    self.pref_items.append({"type": t, "text": v, "surface": surface})

        add_items("興趣")
        add_items("喜好")
        add_items("厭惡")
        add_items("生日")

        if not self.pref_items:
            return

        sentences = [it["surface"] for it in self.pref_items]
        if hasattr(self, 'embedding_fn') and self.embedding_fn:
            embs = np.array([self.embedding_fn(s) for s in sentences], dtype=np.float32)
        else:
            embs = self.embed_model.encode(sentences, convert_to_numpy=True, normalize_embeddings=True).astype('float32')
        self.pref_index.add(embs)
        print(f"✅ 偏好索引建立完成，共 {len(self.pref_items)} 條。")

    def search_preferences(self, query_text, k=5, distance_threshold=None, types=None):
        """
        回傳與 query 最相關的個人偏好（興趣/喜好/厭惡/生日）。
        types: 可傳集合 {"喜好","厭惡","興趣","生日"} 過濾；None 表示不過濾。
        distance_threshold: None 則使用 config 的預設值。
        """
        if self.pref_index.ntotal == 0 or not query_text.strip():
            return []

        if distance_threshold is None:
            distance_threshold = self.default_pref_threshold  # 讀 config 預設

        # 查詢向量
        if hasattr(self, 'embedding_fn') and self.embedding_fn:
            q = np.array([self.embedding_fn(query_text)], dtype=np.float32)
        else:
            q = self.embed_model.encode([query_text], convert_to_numpy=True, normalize_embeddings=True).astype('float32')

        k = min(k, self.pref_index.ntotal)
        D, I = self.pref_index.search(q, k)
        out = []
        for d, i in zip(D[0], I[0]):
            if i < 0 or i >= len(self.pref_items):
                continue
            item = self.pref_items[i]
            if (types is None) or (item["type"] in types):
                if float(d) <= float(distance_threshold):
                    out.append({"type": item["type"], "text": item["text"], "distance": float(d)})
        return out
