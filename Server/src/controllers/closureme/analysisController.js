// analysisController.js
const { spawn } = require("child_process");

let isRunning = false;

exports.runAnalysisTxt = (_req, res) => {
    if (isRunning) {
        return res.status(429).json({ ok: false, error: "analysis running" });
    }
    isRunning = true;

    // const cwd = process.env.ANALYSIS_CWD || "D:/chatbot";
    const cwd = process.env.ANALYSIS_CWD || "D:/chatbot";
    const cmd = process.env.ANALYSIS_CMD || "Analysis_txt.bat";

    const args = ["/c", cmd];
    console.log("[ANALYSIS] spawn:", ["cmd.exe", ...args].join(" "), "cwd=", cwd);

    const child = spawn("cmd.exe", args, {
        cwd,
        windowsHide: false,
        stdio: "inherit",
    });

    const release = () => { isRunning = false; };
    child.on("error", (e) => {
        console.error("[ANALYSIS][ERR]", e);
        release();
        res.status(500).json({ ok: false, error: String(e) });
    });
    child.on("close", (code) => {
        release();
        if (code === 0) res.json({ ok: true });
        else res.status(500).json({ ok: false, code });
    });
};