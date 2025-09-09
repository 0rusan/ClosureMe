# filename: tts_server.py
# Startup warmup + auto-warm after /prepare, port 5009, Unity-compatible
# Now: writes audio to ./out/output.wav on the server and returns a downloadable URL.

import os, io, json, traceback
from pathlib import Path

import torch, soundfile as sf
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename

from TTS_Manager import TTSManager

# ===== Config =====
PORT         = int(os.getenv("PORT", "5009"))
# Write to a server-local folder (NOT Unity's StreamingAssets)
OUTPUT_PATH  = os.environ.get("OUT_WAV", str(Path.cwd() / "out" / "output.wav"))
AUDIO_DIR    = Path(OUTPUT_PATH).parent
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR   = Path(os.getenv("UPLOAD_DIR", str(Path.cwd() / "_uploads")))
DEFAULT_REF  = os.environ.get("REF_WAV", r"C:\Users\wtf81\OneDrive\文件\TTS\晴輝阿姨.aac")
DEFAULT_REF_TEXT = os.environ.get("DEFAULT_REF_TEXT", "")

# Optional: override the public base for audio URLs (e.g., https://tts.example.com/audio)
AUDIO_URL_BASE = os.environ.get("AUDIO_URL_BASE", "")

# Warmup controls
WARMUP_TEXT  = os.environ.get("WARMUP_TEXT", "嗨")
WARMUP_ENABLE = os.environ.get("WARMUP_ENABLE", "1") == "1"

# STT (faster-whisper)
WHISPER_SIZE   = os.environ.get("WHISPER_SIZE", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", ("cuda" if torch.cuda.is_available() else "cpu"))
WHISPER_TYPE   = os.environ.get("WHISPER_TYPE", "float32")

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

app = Flask(__name__)

def _do_warmup(tts: TTSManager, text: str = "嗨"):
    """Synthesize a tiny clip to trigger kernel compilation & caching."""
    if not WARMUP_ENABLE:
        return
    try:
        tmp = UPLOAD_DIR / "_warmup.wav"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        tts.synthesize(
            text=text or "嗨",
            output_path=str(tmp),
            speed=float(os.getenv("F5TTS_DEFAULT_SPEED", "0.90")),
            nfe_step=int(os.getenv("F5TTS_NFE", "16")),
            cross_fade_sec=float(os.getenv("F5TTS_XFADE", "0.12")),
            pause_ms=int(os.getenv("F5TTS_PAUSE_MS", "0")),
            strip_meta=True,
            taiwan_accent=True,
            remove_silence=False,
            seed=1,
            ref_text=os.environ.get("DEFAULT_REF_TEXT", ""),
        )
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        print("Warmup OK.")
    except Exception as e:
        print(f"[WARN] warmup failed: {e}")

# ===== Init TTS =====
tts = TTSManager()
if DEFAULT_REF and os.path.isfile(DEFAULT_REF):
    try:
        tts.prepare_reference(DEFAULT_REF, ref_text=DEFAULT_REF_TEXT)
        print(f"OK TTS ref ready: {DEFAULT_REF}")
        _do_warmup(tts, WARMUP_TEXT)
    except Exception as e:
        print(f"[WARN] ref load failed: {e}")
else:
    print("[WARN] REF_WAV not set. POST /prepare or set env REF_WAV.")

# ===== Init STT =====
if WhisperModel is not None:
    print(f"OK STT: faster-whisper/{WHISPER_SIZE} on {WHISPER_DEVICE} ({WHISPER_TYPE})")
    stt_model = WhisperModel(WHISPER_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_TYPE)
else:
    print("WARN: faster-whisper not installed, /stt will error")
    stt_model = None

def _normalize_text(payload) -> str:
    text = (payload or {}).get("text", "")
    if isinstance(text, (list, tuple)):
        flat, stack = [], list(text)
        while stack:
            x = stack.pop(0)
            if isinstance(x, (list, tuple)):
                stack = list(x) + stack
            else:
                flat.append(str(x))
        text = " ".join(s.strip() for s in flat if str(s).strip())
    elif not isinstance(text, str):
        text = str(text)
    return text.strip()

@app.get("/health")
def health():
    # Also show the public URL where audio is served
    name = Path(OUTPUT_PATH).name
    if AUDIO_URL_BASE:
        audio_url = AUDIO_URL_BASE.rstrip("/") + "/" + name
    else:
        audio_url = f"{request.scheme}://{request.host}/audio/{name}"
    return jsonify({
        "ok": True,
        "tts_prepared": tts.prepared,
        "stt_model": f"faster-whisper/{WHISPER_SIZE}",
        "stt_device": WHISPER_DEVICE,
        "output_path": OUTPUT_PATH,
        "audio_url": audio_url,
        "warmup": dict(enabled=WARMUP_ENABLE, text=WARMUP_TEXT)
    })

@app.post("/prepare")
def prepare():
    """Prepare or switch reference audio; auto-warm afterwards."""
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        if "wav" in request.files:
            f = request.files["wav"]
            path = UPLOAD_DIR / secure_filename(f.filename or "ref.wav")
            f.save(path)
            ref_text = request.form.get("ref_text", "")
            tts.prepare_reference(str(path), ref_text=ref_text)
            _do_warmup(tts, WARMUP_TEXT)
            print(f"[TTS][PREPARED] ref_wav={path} ref_text_used={bool(ref_text)}")
            return jsonify({"ok": True, "ref_wav": str(path), "ref_text_used": bool(ref_text)})

        data = request.get_json(silent=True) or {}
        wav_path = data.get("wav_path")
        ref_text = data.get("ref_text", "")
        if not wav_path or not os.path.isfile(wav_path):
            return jsonify({"ok": False, "error": "缺少或無效的參考音"}), 400
        tts.prepare_reference(wav_path, ref_text=ref_text)
        _do_warmup(tts, WARMUP_TEXT)
        print(f"[TTS][PREPARED] ref_wav={wav_path} ref_text_used={bool(ref_text)}")
        return jsonify({"ok": True, "ref_wav": wav_path, "ref_text_used": bool(ref_text)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": repr(e)}), 400


@app.post("/tts")
def tts_route():
    """Unity JSON {text: '...'} -> synthesize to OUTPUT_PATH and return a URL to fetch it."""
    try:
        data = request.get_json(silent=True) or {}
        text = _normalize_text(data)
        if not text:
            return jsonify({"ok": False, "error": "text is empty"}), 400

        # If not prepared, try auto-prepare with DEFAULT_REF once
        if not tts.prepared:
            if DEFAULT_REF and os.path.isfile(DEFAULT_REF):
                tts.prepare_reference(DEFAULT_REF, ref_text=DEFAULT_REF_TEXT)
                _do_warmup(tts, WARMUP_TEXT)
            else:
                return jsonify({"ok": False, "error": "no reference voice: set REF_WAV or POST /prepare"}), 400

        out_path = OUTPUT_PATH
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        tts.synthesize(
            text=text,
            output_path=out_path,
            speed=float(os.getenv("F5TTS_DEFAULT_SPEED", "0.90")),
            nfe_step=int(os.getenv("F5TTS_NFE", "16")),
            cross_fade_sec=float(os.getenv("F5TTS_XFADE", "0.12")),
            pause_ms=int(os.getenv("F5TTS_PAUSE_MS", "400")),
            strip_meta=os.getenv("F5TTS_STRIP_META", "true").lower()=="true",
            taiwan_accent=True,
            remove_silence=False,
            seed=int(data.get("seed", -1)),
            ref_text=str(data.get("ref_text", "") or ""),
        )

        # Build a downloadable URL for Unity to fetch the wav
        name = Path(out_path).name
        if AUDIO_URL_BASE:
            audio_url = AUDIO_URL_BASE.rstrip("/") + "/" + name
        else:
            audio_url = f"{request.scheme}://{request.host}/audio/{name}"

        return jsonify({"ok": True, "output": out_path, "url": audio_url})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": repr(e)}), 500

# 需要：from flask import request, jsonify  已經有就不用再加
@app.post("/prepare-notify")
def prepare_notify():
    data = request.get_json(silent=True) or {}
    voice_name = data.get("voice_name")
    source_path = data.get("source_path")
    md5 = data.get("md5")
    mtime = data.get("mtime")

    print(f"[TTS][SWITCHED] voice={voice_name} src={source_path} md5={md5} mtime={mtime}")
    reload_reference(force=True)     # ← 立即重載
    _do_warmup(tts, WARMUP_TEXT)     # ← 立刻做一次暖機，之後就用新聲音
    return jsonify({"ok": True})

@app.post("/stt")
def stt_route():
    try:
        if stt_model is None:
            return Response(json.dumps({"ok": False, "error": "faster-whisper 未安裝"}),
                            content_type="application/json; charset=utf-8", status=500)
        if "audio" not in request.files:
            return Response(json.dumps({"ok": False, "error": "缺少 audio 檔"}),
                            content_type="application/json; charset=utf-8", status=400)
        data = io.BytesIO(request.files["audio"].read())
        audio, sr = sf.read(data)
        segments, info = stt_model.transcribe(audio, beam_size=1, language="zh")
        text = "".join([seg.text for seg in segments]).strip()
        return Response(json.dumps({"ok": True, "text": text}, ensure_ascii=False),
                        content_type="application/json; charset=utf-8")
    except Exception as e:
        traceback.print_exc()
        return Response(json.dumps({"ok": False, "error": repr(e)}, ensure_ascii=False),
                        content_type="application/json; charset=utf-8", status=500)

@app.get("/audio/<path:filename>")
def get_audio(filename):
    # Serve the audio directory read-only
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/wav", as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)