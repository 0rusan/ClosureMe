const fs = require("fs");
const path = require("path");

const ALLOWED = new Set(["MeetingRoom", "Park", "Library"]);

exports.writeEnvironment = async (req, res) => {
  try {
    const { environment } = req.body;
    const userId = req.user_id;

    if (!userId) {
      return res.status(401).json({ message: "未授權存取" });
    }

    if (!environment || !ALLOWED.has(environment)) {
      return res.status(400).json({ message: "無效的環境參數" });
    }

    const outputDir = "D:/model/AIAgentModel"; 
    fs.mkdirSync(outputDir, { recursive: true });

    const filePath = path.join(outputDir, "environment.txt");
    fs.writeFileSync(filePath, environment, { encoding: "utf8" });

    return res.json({
      message: " 環境檔案已寫入",
      output: { environment, filePath }
    });
  } catch (err) {
    console.error("writeEnvironment error:", err);
    return res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};