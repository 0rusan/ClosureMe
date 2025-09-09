# -*- coding: utf-8 -*-
"""
共同回憶整理工具（CLI 版，無 GUI）
- 讀取一個 {角色名}.txt（每行 = 一段共同回憶）
- 以 OpenAI GPT 逐段濃縮（若有 API key），保留日期、不重複
- 追加寫入到 shared_memories/shared_memories_{角色名}.txt
- 也提供 process_file(input_path) 供他系統程式化呼叫
"""
import os
import re
import json
import argparse
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
from datetime import datetime

# ===================== 設定 =====================
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
CONFIG = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)

MODEL_NAME = CONFIG.get("model_name", "gpt-4.1-nano")
OPENAI_API_KEY = (CONFIG.get("openai_api_key") or "").strip() if CONFIG else ""
AVOID_DUP_IN_FILE = bool(CONFIG.get("avoid_duplicates_in_file", True)) if CONFIG else True

BASE_DIR = Path(__file__).resolve().parent
SHARED_DIR = BASE_DIR / "shared_memories"
SHARED_DIR.mkdir(parents=True, exist_ok=True)

# ===================== OpenAI（可選） =====================
USE_OPENAI = False
try:
    import openai  # pip install openai
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
        USE_OPENAI = True
except Exception:
    USE_OPENAI = False

# ===================== 資料模型 =====================
@dataclass
class MemoryItem:
    summary: str
    detail: str

# ===================== 正則（日期/時間） =====================
RE_DATE_YMD = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")  # 2025-08-30 / 2025/08/30
RE_DATE_MD  = re.compile(r"\b\d{1,2}/\d{1,2}\b")               # 8/30
RE_DATE_CJK = re.compile(r"\b\d{1,2}月\d{1,2}日\b")            # 8月30日
RE_TIME_HM  = re.compile(r"^\s*\d{1,2}:\d{2}\s+")              # 行首 HH:MM

def extract_dates(s: str) -> List[str]:
    dates = set()
    for pat in (RE_DATE_YMD, RE_DATE_MD, RE_DATE_CJK):
        for m in pat.finditer(s):
            dates.add(m.group(0))
    return sorted(dates)

# ===================== 工具 =====================
def role_from_filename(path: Path) -> str:
    """
    由輸入檔名取得角色名：
      媽咪🫶.txt → 媽咪🫶
      [LINE]媽咪🫶.txt → 媽咪🫶
    """
    stem = path.stem
    stem = re.sub(r"^\s*\[.*?\]\s*", "", stem).strip()
    return stem or "default"

def get_output_path(role: str) -> Path:
    safe_role = re.sub(r"[\\/]+", "_", role.strip() or "default")
    return SHARED_DIR / f"shared_memories_{safe_role}.txt"

def normalize_key(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())

def deduplicate_items(items: List[MemoryItem]) -> List[MemoryItem]:
    seen, out = set(), []
    for it in items:
        key = normalize_key(it.detail)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def filter_out_existing(path: Path, items: List[MemoryItem]) -> List[MemoryItem]:
    if not (AVOID_DUP_IN_FILE and path.exists()):
        return items
    existed = set()
    try:
        with path.open("r", encoding="utf-8") as fr:
            for line in fr:
                parts = line.rstrip("\n").split("\t", 1)
                if len(parts) == 2:
                    existed.add(normalize_key(parts[1]))  # 以 detail 去重
    except Exception:
        pass
    return [it for it in items if normalize_key(it.detail) not in existed]

# ===================== LLM 濃縮（逐段，保留日期） =====================
PROMPT_SYS = (
    "你是共同回憶整理助手。以下輸入為多段『粗略共同回憶』，每行一段。\n"
    "請逐段整理重點，輸出 JSON 陣列（若內容極短/無意義可跳過，不要合併不同段落）。\n"
    "規則：\n"
    "1) 若原句含『日期』(YYYY/MM/DD、YYYY-MM-DD、MM/DD、M月D日)，請原樣保留在 summary 與 detail 中；\n"
    "2) 移除行首『時間 HH:MM』與稱呼/名字等噪音（若可辨識），但不要改動日期；\n"
    "3) 不要發明不存在的日期與細節；\n"
    "4) 每項：{ \"summary\": \"20~40字摘要（若有日期可包含）\", \"detail\": \"1~2句完整描述（務必保留原句日期）\" }；\n"
    "5) 僅輸出 JSON，勿加任何解說。"
)

def _safe_json_block(s: str) -> str:
    s = (s or "").replace("\r", " ").replace("\n", " ").strip()
    m = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", s)
    return m.group(0) if m else "[]"

def llm_summarize_lines(lines: List[str]) -> List[MemoryItem]:
    if not USE_OPENAI:
        # 本地保底：去掉行首 HH:MM；summary 取前 40 字
        items = []
        for raw in lines:
            txt = raw.strip()
            if not txt:
                continue
            txt = RE_TIME_HM.sub("", txt)
            summ = txt[:40] + ("…" if len(txt) > 40 else "")
            items.append(MemoryItem(summary=summ, detail=txt))
        return deduplicate_items(items)

    try:
        payload = "\n".join(lines)
        messages = [
            {"role": "system", "content": PROMPT_SYS},
            {"role": "user",   "content": f"請整理下列多段共同回憶（每行一段）：\n{payload}"}
        ]
        resp = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
        )
        content = _safe_json_block(resp.choices[0].message.content)
        data = json.loads(content)
        items: List[MemoryItem] = []
        for obj in data:
            summ = (obj.get("summary") or "").strip()
            det  = (obj.get("detail") or "").strip()
            if not summ or not det:
                continue
            # 若 detail 無日期，但原輸入整體有日期 → 補救（取最常見的第一個）
            if not (RE_DATE_YMD.search(det) or RE_DATE_MD.search(det) or RE_DATE_CJK.search(det)):
                all_dates = []
                for ln in lines:
                    all_dates += extract_dates(ln)
                if all_dates:
                    det  = f"{all_dates[0]} {det}"
                    summ = f"{all_dates[0]} " + summ
            items.append(MemoryItem(
                summary=summ[:40] + ("…" if len(summ) > 40 else ""),
                detail=det
            ))
        return deduplicate_items(items)
    except Exception as e:
        print("[WARN] OpenAI 濃縮失敗，改用本地保底：", e)
        # fallback
        items = []
        for raw in lines:
            txt = raw.strip()
            if not txt:
                continue
            txt = RE_TIME_HM.sub("", txt)
            summ = txt[:40] + ("…" if len(txt) > 40 else "")
            items.append(MemoryItem(summary=summ, detail=txt))
        return deduplicate_items(items)

# ===================== 寫檔 =====================
def append_shared_memories(role: str, memories: List[MemoryItem]) -> Tuple[Path, int]:
    out_path = get_output_path(role)

    # 過濾已存在的重複
    memories = filter_out_existing(out_path, memories)

    # 確保檔尾換行
    needs_nl = False
    if out_path.exists():
        try:
            with out_path.open("rb") as frb:
                frb.seek(max(frb.seek(0, os.SEEK_END) or 0 - 1, 0))
                last = frb.read() or b""
                needs_nl = (not last.endswith(b"\n"))
        except Exception:
            needs_nl = False

    cnt = 0
    with out_path.open("a", encoding="utf-8") as fw:
        if needs_nl:
            fw.write("\n")
        for m in memories:
            summary = m.summary.replace("\t", " ").strip()
            detail  = m.detail.replace("\t", " ").strip()
            if not summary or not detail:
                continue
            fw.write(f"{summary}\t{detail}\n")
            cnt += 1
    return out_path, cnt

# ===================== 核心流程 =====================
def process_file(input_path: str) -> Tuple[str, int, List[MemoryItem]]:
    """
    讀取 {角色名}.txt → 每行一段 → 濃縮 → 追加寫入 shared_memories/shared_memories_{角色名}.txt
    回傳：(輸出檔路徑, 寫入筆數, 寫入內容列表)
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到輸入檔：{path}")

    role = role_from_filename(path)

    # 讀行（多編碼嘗試）
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8", "utf-8-sig", "cp950", "big5", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")

    # 依換行分段
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return str(get_output_path(role)), 0, []

    # LLM 濃縮 / 本地保底
    items = llm_summarize_lines(lines)
    if not items:
        return str(get_output_path(role)), 0, []

    # 寫入
    out_path, n = append_shared_memories(role, items)
    return str(out_path), n, items

# ===================== CLI =====================
def main():
    # 先宣告 global，避免 "used prior to global declaration"
    global MODEL_NAME

    import argparse
    parser = argparse.ArgumentParser(description="共同回憶整理（CLI 版）")

    # 改成旗標式輸入，符合你的呼叫方式
    parser.add_argument("--input", "-i", required=True,
                        help="{角色名}.txt 檔案路徑（每行一段共同回憶）")

    # default 改成 None，避免在宣告 global 前引用 MODEL_NAME
    parser.add_argument("--model", default=None,
                        help="OpenAI 模型名稱（若不指定則使用 config.json 的 model_name）")

    args = parser.parse_args()

    # 若有指定 --model，才覆寫全域 MODEL_NAME
    if args.model:
        MODEL_NAME = args.model

    print(f"[INFO] OpenAI={'ON' if USE_OPENAI else 'OFF'} | Model={MODEL_NAME}")
    out_path, n, items = process_file(args.input)

    print(f"[OK] 已寫入：{out_path}，共 {n} 筆")
    for it in items:
        print(f"- {it.summary}\t{it.detail}")


if __name__ == "__main__":
    main()
