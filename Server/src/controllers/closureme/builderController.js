// controllers/closureme/builderController.js
const { spawn } = require("child_process");

exports.buildAgentBundle = (_req, res) => {
    const cwd = process.env.BUILDER_CWD || "D:/builder";
    const batPath = process.env.BUILDER_BAT || "build_agent_bundle.bat";
    const args = ["/c", batPath];

    console.log("[BUILDER] spawn:", args.join(" "));
    const child = spawn("cmd.exe", args, {
        cwd,
        windowsHide: false,
        stdio: "inherit",
    });

    child.on("error", e =>
        res.status(500).json({ ok: false, error: String(e) })
    );
    child.on("close", code =>
        code === 0
            ? res.json({ ok: true })
            : res.status(500).json({ ok: false, code })
    );
};
