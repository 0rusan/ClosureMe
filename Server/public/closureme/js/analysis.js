// analysis.js
export async function runAnalysisTxt() {
    const res = await fetch("/api/analysis-txt", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${localStorage.getItem("token")}`
        },
        body: "{}",
    });
    const j = await res.json().catch(() => ({}));
    if (!res.ok || j.ok === false) {
        throw new Error(j.error || j.err || `HTTP ${res.status}`);
    }
    return j;
}