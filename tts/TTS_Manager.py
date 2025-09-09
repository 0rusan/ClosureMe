# filename: TTS_Manager.py
# F5-TTS manager: compatible signatures + ref-audio tail clean + optional pad + output fadeout

import os, re
from typing import Optional, List
from pathlib import Path
from contextlib import nullcontext

import numpy as np
import torch
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from cached_path import cached_path

from f5_tts.infer.utils_infer import (
    preprocess_ref_audio_text, load_model, load_vocoder, infer_process,
)
from f5_tts.model import DiT

torch.set_float32_matmul_precision("high")
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

# ====== Parameters (env overridable) ======
SWAPS_PATH  = Path(os.getenv("F5TTS_SWAPS", str(Path(__file__).parent / "swaps.txt")))
MODEL_NAME  = os.getenv("F5TTS_MODEL", "F5TTS_v1_Base")
CKPT_FILE   = os.getenv("F5TTS_CKPT",  "hf://SWivid/F5-TTS/F5TTS_v1_Base/model_1250000.safetensors")
VOCAB_FILE  = os.getenv("F5TTS_VOCAB", "hf://SWivid/F5-TTS/F5TTS_v1_Base/vocab.txt")

DEFAULT_SPEED   = float(os.getenv("F5TTS_DEFAULT_SPEED", "0.90"))
DEFAULT_NFE     = int(os.getenv("F5TTS_NFE", "16"))
DEFAULT_XFADE   = float(os.getenv("F5TTS_XFADE", "0.12"))
DEFAULT_PAUSEMS = int(os.getenv("F5TTS_PAUSE_MS", "400"))
REMOVE_SIL_DEF  = os.getenv("F5TTS_REMOVE_SIL", "false").lower() == "true"

CHUNK_MIN = int(os.getenv("F5TTS_CHUNK_MIN", "22"))
CHUNK_MAX = int(os.getenv("F5TTS_CHUNK_MAX", "160"))

SIL_MIN_MS     = int(os.getenv("F5TTS_SIL_MIN_MS", "120"))
SIL_THRESH_REL = float(os.getenv("F5TTS_SIL_THRESH_DB", "-30"))
SIL_BACKOFF_MS = int(os.getenv("F5TTS_SIL_BACKOFF_MS", "20"))
REF_FADEIN_MS  = int(os.getenv("F5TTS_REF_FADEIN_MS", "8"))
REF_FADEOUT_MS = int(os.getenv("F5TTS_REF_FADEOUT_MS", "12"))
REF_MAX_VOICE_MS = int(os.getenv("F5TTS_REF_MAX_VOICE_MS", "10000"))  # limit voice part to 10s
REF_TAIL_SIL_MS  = int(os.getenv("F5TTS_REF_TAIL_SIL_MS", "2000"))    # add 2s silence tail

TRIM_LEAD_MS   = int(os.getenv("F5TTS_TRIM_LEAD_MS", "80"))
OUT_FADEIN_MS  = int(os.getenv("F5TTS_FADEIN_MS", "8"))
OUT_FADEOUT_MS = int(os.getenv("F5TTS_FADEOUT_MS", "24"))
LEAD_REL_EPS   = float(os.getenv("F5TTS_LEAD_REL_EPS", "0.01"))

_DIRECTIVE_KEYWORDS = "語速|速度|停頓|語氣|情緒|情感|節奏|台灣|臺灣|口語|自然|無兒化|tone|style|慢|快".split("|")
_BRACKET_PAIRS = [("（","）"),("(",")"),("[","]")]

def _strip_directives(text: str) -> str:
    if not text: return text
    t = text.strip()
    while True:
        removed = False
        for l, r in _BRACKET_PAIRS:
            if t.startswith(l) and r in t:
                seg = t[t.find(l)+1:t.find(r)]
                if any(k in seg for k in _DIRECTIVE_KEYWORDS):
                    t = t[t.find(r)+1:].lstrip(); removed = True
        if not removed: break
    def _rm(m):
        seg = m.group(1)
        return "" if any(k in seg for k in _DIRECTIVE_KEYWORDS) else m.group(0)
    t = re.sub(r"（([^）]{1,120})）", _rm, t)
    t = re.sub(r"\(([^)]{1,120})\)", _rm, t)
    t = re.sub(r"\[([^\]]{1,120})\]", _rm, t)
    return re.sub(r"\s+", " ", t).strip()

def _normalize_text(text: str) -> str:
    if not text: return ""
    t = re.sub(r"[\u00A0\u2000-\u200B\u3000]", " ", text)
    t = re.sub(r"[~～]+", "，", t)
    t = re.sub(r"[—–-]{2,}", "—", t)
    lines = [ln.strip() for ln in t.replace("\r\n","\n").replace("\r","\n").split("\n")]
    fixed = []
    for ln in lines:
        if not ln: continue
        if not re.search(r"[。！？!?]$", ln): ln += "。"
        fixed.append(ln)
    return "\n".join(fixed)

class _SwapRule:
    def __init__(self, pattern: str, replacement: str, is_regex: bool):
        self.replacement = replacement
        self.rx = re.compile(pattern) if is_regex else re.compile(re.escape(pattern))
    def apply(self, s: str) -> str:
        return self.rx.sub(self.replacement, s)

def _load_swaps(path: Path):
    rules = []
    if not path.is_file():
        return rules
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue
            pat, rep = line.split("=>", 1)
            pat = pat.strip()
            rep = rep.split("#", 1)[0].strip()
            is_regex = False
            if pat.startswith("re:"):
                pat = pat[3:].strip()
                is_regex = True
            if rep == "":
                continue
            rules.append(_SwapRule(pat, rep, is_regex))
    return rules

def _apply_swaps(text: str, rules) -> str:
    out = text
    for r in rules:
        out = r.apply(out)
    return out

def _smart_segment(text: str, min_chars=CHUNK_MIN, max_chars=CHUNK_MAX) -> List[str]:
    raw = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not raw:
        raw = [seg.strip() for seg in re.split(r"(?<=[。！？!?])\s+", text) if seg.strip()]
    merged, buf = [], ""
    for seg in raw:
        if len(buf) + len(seg) <= max_chars:
            buf = (buf + " " + seg).strip() if buf else seg
        else:
            if buf: merged.append(buf)
            buf = seg
    if buf: merged.append(buf)
    out = []
    for seg in merged:
        if out and len(seg) < min_chars:
            out[-1] = (out[-1] + " " + seg).strip()
        else:
            out.append(seg)
    return out

def _resolve_path(p: Optional[str]) -> Optional[str]:
    if not p: return None
    return str(cached_path(p)) if p.startswith("hf://") else p

class TTSManager:
    """F5-TTS manager: keep old method signatures to avoid TypeError."""
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"OK F5-TTS device: {self.device}{' - ' + torch.cuda.get_device_name(0) if self.device=='cuda' else ''}")
        self.ref_wav_path = "temp_ref.wav"
        self.prepared = False
        self._swap_rules = _load_swaps(SWAPS_PATH)
        self._load_models()

    def _load_models(self):
        ckpt  = _resolve_path(CKPT_FILE)
        vocab = _resolve_path(VOCAB_FILE)
        self.vocoder = load_vocoder()
        self.ema_model = load_model(
            DiT,
            dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
            ckpt,
            vocab_file=vocab,
        )
        if self.device == "cuda":
            self.ema_model.to(dtype=torch.float16)
        print(f"OK Model loaded: {MODEL_NAME} | ckpt={ckpt}")
        print(f"OK swaps: {SWAPS_PATH} ({len(self._swap_rules)} rules)")

    def prepare_reference(self, wav_file: str, ref_text: str = ""):
        """Prepare reference audio: trim head/tail, limit voice, add tail silence and fades."""
        if not os.path.isfile(wav_file):
            raise FileNotFoundError(f"找不到參考音檔：{wav_file}")
        audio = AudioSegment.from_file(wav_file).set_frame_rate(24000).set_channels(1)

        # Detect non-silent spans to trim head & tail
        thresh = audio.dBFS + SIL_THRESH_REL
        nonsil = detect_nonsilent(audio, min_silence_len=SIL_MIN_MS, silence_thresh=thresh)
        if nonsil:
            start_ms = max(0, nonsil[0][0] - SIL_BACKOFF_MS)
            end_ms   = min(len(audio), nonsil[-1][1] + SIL_BACKOFF_MS)
            audio = audio[start_ms:end_ms]

        # Limit the speech portion to REF_MAX_VOICE_MS, then append REF_TAIL_SIL_MS silence
        if REF_MAX_VOICE_MS > 0:
            audio = audio[:REF_MAX_VOICE_MS]
        if REF_TAIL_SIL_MS > 0:
            audio += AudioSegment.silent(duration=REF_TAIL_SIL_MS)

        # Fades
        if REF_FADEIN_MS > 0:
            audio = audio.fade_in(REF_FADEIN_MS)
        if REF_FADEOUT_MS > 0:
            audio = audio.fade_out(REF_FADEOUT_MS)

        audio.export(self.ref_wav_path, format="wav")
        self.prepared = True
        print("Ref ready (trimmed + tail pad).")

    def _process_text(self, text: str, *, strip_meta=True) -> List[str]:
        t = (text or "").strip()
        if strip_meta:
            t = _strip_directives(t)
        t = _normalize_text(t)
        t2 = _apply_swaps(t, self._swap_rules)
        return _smart_segment(t2, CHUNK_MIN, CHUNK_MAX)

    def synthesize(self,
                   text: str,
                   output_path: str,
                   *,
                   speed: float = DEFAULT_SPEED,
                   nfe_step: int = DEFAULT_NFE,
                   cross_fade_sec: float = DEFAULT_XFADE,
                   pause_ms: int = DEFAULT_PAUSEMS,
                   ref_text: str = "",
                   strip_meta: bool = True,
                   taiwan_accent: bool = True,   # kept for compatibility (ignored)
                   remove_silence: bool = REMOVE_SIL_DEF,
                   seed: int = -1) -> str:
        """Synthesize to output_path and return the actual path."""
        if not self.prepared:
            raise RuntimeError("請先 prepare_reference() 準備參考音")
        if not text or not text.strip():
            raise ValueError("text 不可為空")

        lines = self._process_text(text, strip_meta=strip_meta)
        if not lines:
            raise ValueError("處理後文字為空")

        if seed < 0 or seed > 2**31 - 1:
            seed = int(np.random.randint(0, 2**31 - 1))
        torch.manual_seed(seed)

        ref_audio_ready, ref_text_ready = preprocess_ref_audio_text(self.ref_wav_path, ref_text or "")
        waves, sr_final = [], 24000

        use_amp = torch.cuda.is_available()
        amp_dtype = torch.float16
        with torch.inference_mode():
            ctx = torch.cuda.amp.autocast(dtype=amp_dtype) if use_amp else nullcontext()
            with ctx:
                for seg in lines:
                    w, sr, _ = infer_process(
                        ref_audio_ready, ref_text_ready, seg,
                        self.ema_model, self.vocoder,
                        cross_fade_duration=float(cross_fade_sec),
                        nfe_step=int(nfe_step),
                        speed=float(speed),
                        show_info=lambda *a, **k: None,
                        progress=None,
                    )
                    sr_final = sr
                    waves.append(w)

        if not waves:
            raise RuntimeError("無法生成音訊，請檢查輸入")

        gap = np.zeros(int(sr_final * (max(0, pause_ms) / 1000.0)), dtype=waves[0].dtype) if pause_ms > 0 else None
        parts = []
        for i, w in enumerate(waves):
            parts.append(w)
            if gap is not None and i < len(waves) - 1:
                parts.append(gap)
        final_wave = np.concatenate(parts) if len(parts) > 1 else waves[0]

        if TRIM_LEAD_MS > 0 and len(final_wave) > 0:
            sr = sr_final
            n = min(len(final_wave), int(sr * TRIM_LEAD_MS / 1000))
            if n > 8:
                head = final_wave[: n // 2]
                peak = np.max(np.abs(final_wave))
                if peak > 0 and np.max(np.abs(head)) < LEAD_REL_EPS * peak:
                    final_wave = final_wave[n:]
                    print(f"Trim head {TRIM_LEAD_MS} ms low-energy")

        if OUT_FADEIN_MS > 0 and len(final_wave) > 0:
            sr = sr_final
            m = min(len(final_wave), int(sr * OUT_FADEIN_MS / 1000))
            if m > 1:
                ramp = np.linspace(0.0, 1.0, m, dtype=np.float32)
                x = final_wave.astype(np.float32)
                x[:m] = x[:m] * ramp
                final_wave = x.astype(final_wave.dtype)
                print(f"Fade-in {OUT_FADEIN_MS} ms")

        if OUT_FADEOUT_MS > 0 and len(final_wave) > 0:
            sr = sr_final
            m = min(len(final_wave), int(sr * OUT_FADEOUT_MS / 1000))
            if m > 1:
                ramp = np.linspace(1.0, 0.0, m, dtype=np.float32)
                x = final_wave.astype(np.float32)
                x[-m:] = x[-m:] * ramp
                final_wave = x.astype(final_wave.dtype)
                print(f"Fade-out {OUT_FADEOUT_MS} ms")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, final_wave, sr_final)
        print(f"OK wrote: {output_path}")
        return output_path