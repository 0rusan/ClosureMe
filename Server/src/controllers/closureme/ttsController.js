const { spawn } = require("child_process");

exports.prepareTTS = (_req, res) => {
    // const cwd = process.env.TTS_CWD || "D:/tts";
    const cwd = process.env.TTS_CWD || "D:/tts";
    const batPath = process.env.TTS_PREPARE_BAT || "tts_prepare_and_tts.cmd";
    const args = ["/c", batPath];

    console.log("[TTS] prepare spawn:", args.join(" "));
    const child = spawn("cmd.exe", args, {
        cwd,
        windowsHide: false,
        stdio: "inherit",
    });

    child.on("error", e => res.status(500).json({ ok: false, error: String(e) }));
    child.on("close", code => code === 0
        ? res.json({ ok: true })
        : res.status(500).json({ ok: false, code })
    );
};