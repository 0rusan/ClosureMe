// tts.js
export async function runTTS() {
    const res = await fetch("/api/tts-prepare", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${localStorage.getItem("token")}`
        }
    });
    const j = await res.json();
    if (!res.ok || !j.ok) throw new Error(j.error || j.err || `HTTP ${res.status}`);
}