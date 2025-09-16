// characterController.js 
const pool = require("../../models/db");
const path = require("path");
const fs = require("fs").promises;
const { MODE, uploadBufferToS3 } = require("../../storage");
const https = require("https");
const http = require("http");
const { v4: uuidv4 } = require("uuid");
const { spawn } = require("child_process");

/** ---------------------------
 * 共用工具
 * -------------------------- */
function toSafeBaseName(name) {
  let base = String(name || "")
    .replace(/\.[^.]+$/, "")
    .replace(/\s+/g, "_")
    .replace(/[^\w\u4e00-\u9fa5-]+/g, "")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return base || "file";
}

// 檔名不重複
async function getUniqueFileNameFromDB(baseName, ext) {
  const base = toSafeBaseName(baseName);
  const safeExt = (ext || ".png").toLowerCase();

  const pattern = `^${base}(?:\\([0-9]+\\))?\\.[A-Za-z0-9]+$`;
  const result = await pool.query(
    `SELECT file_name FROM char_images WHERE file_name ~ $1`,
    [pattern]
  );
  const existing = new Set(result.rows.map((r) => r.file_name.toLowerCase()));

  let i = 0,
    candidate;
  do {
    candidate = i === 0 ? `${base}${safeExt}` : `${base}(${i})${safeExt}`;
    i++;
  } while (existing.has(candidate.toLowerCase()));

  return candidate;
}

// 由 imageId 反推「角色基底名」
async function getBaseNameByImageId(imageId) {
  const r = await pool.query(
    `SELECT file_name, role_type FROM char_images WHERE id = $1`,
    [imageId]
  );
  if (!r.rowCount) throw new Error("找不到對應的主圖 (imageId)");
  const { file_name, role_type } = r.rows[0];
  const base =
    role_type && role_type !== "main"
      ? file_name.split("_", 1)[0]
      : file_name.split(".", 1)[0];
  return toSafeBaseName(base);
}

const uploadDir = path.join(__dirname, "../../../public/uploads");

/** ---------------------------
 * header 安全處理工具
 * -------------------------- */
function sanitizeAsciiFilename(name) {
  const cleaned = String(name).replace(/[\r\n"]/g, "_");
  return cleaned.replace(/[^\x20-\x7E]/g, "_").replace(/[\\\/:*?<>|]/g, "_");
}

function encodeRFC5987(str) {
  return encodeURIComponent(str)
    .replace(/['()]/g, escape)
    .replace(/\*/g, "%2A")
    .replace(/%(7C|60|5E)/g, "%25$1");
}

function setDownloadHeaders(res, filename, contentType, contentLength) {
  const ascii = sanitizeAsciiFilename(filename);
  const utf8 = encodeRFC5987(filename);
  res.setHeader("Content-Type", contentType || "application/octet-stream");
  res.setHeader(
    "Content-Disposition",
    `attachment; filename="${ascii}"; filename*=UTF-8''${utf8}`
  );
  if (contentLength && Number.isFinite(Number(contentLength))) {
    res.setHeader("Content-Length", String(contentLength));
  }
}

// 儲存人物資訊：profile/memory/voice
exports.saveCharacterInfo = async (req, res) => {
  try {
    const userId = req.user_id;
    const imageId = req.body.imageId;
    const profileRaw = (req.body.profile ?? "").toString();
    const memoryRaw = (req.body.memory ?? "").toString();
    const voice = (req.files?.voice && req.files.voice[0]) || null;

    if (!userId || !imageId) {
      return res.status(400).json({ message: "缺少 imageId" });
    }

    if (!voice) {
      return res.status(400).json({ message: " 必須上傳 wav 語音檔" });
    }
    const voiceName = (voice.originalname || "").toLowerCase();
    const voiceIsWavExt = voiceName.endsWith(".wav");
    const voiceIsWavType = ["audio/wav", "audio/x-wav"].includes(
      (voice.mimetype || "").toLowerCase()
    );
    if (!voiceIsWavExt && !voiceIsWavType) {
      return res.status(400).json({ message: " 語音檔必須是 .wav 格式" });
    }

    const base = await getBaseNameByImageId(imageId);

    const toPrettyJsonBuffer = (text) => {
      let obj;
      try { obj = JSON.parse(text); } catch { obj = { text: text }; }
      return Buffer.from(JSON.stringify(obj, null, 2), "utf-8");
    };

    await pool.query(`DELETE FROM char_profile WHERE image_id=$1`, [imageId]);
    await pool.query(`DELETE FROM char_memory  WHERE image_id=$1`, [imageId]);
    await pool.query(`DELETE FROM char_voice   WHERE image_id=$1`, [imageId]);

    const profileKey = `uploads/${base}_profile.json`;
    const profileUrl = await uploadBufferToS3({
      buffer: toPrettyJsonBuffer(profileRaw),
      key: profileKey,
      contentType: "application/json",
    });
    await pool.query(
      `INSERT INTO char_profile (image_id, file_path) VALUES ($1,$2)`,
      [imageId, profileUrl]
    );

    const memoryKey = `uploads/${base}_memory.txt`;
    const memoryUrl = await uploadBufferToS3({
      buffer: Buffer.from(memoryRaw, "utf-8"),
      key: memoryKey,
      contentType: "text/plain",
    });
    await pool.query(
      `INSERT INTO char_memory (image_id, file_path) VALUES ($1,$2)`,
      [imageId, memoryUrl]
    );

    const voiceKey = `uploads/${base}_voice.wav`;
    const voiceUrl = await uploadBufferToS3({
      buffer: voice.buffer,
      key: voiceKey,
      contentType: "audio/wav",
    });
    await pool.query(
      `INSERT INTO char_voice (image_id, file_path) VALUES ($1,$2)`,
      [imageId, voiceUrl]
    );

    return res.json({ message: "人物資訊已保存（JSON 內容 & 防快取）" });
  } catch (err) {
    console.error("saveCharacterInfo error:", err);
    return res.status(500).json({ message: "保存失敗", error: err.message });
  }
};

// 上傳 3D 模型
exports.uploadModel = async (req, res) => {
  try {
    const userId = req.user_id;
    const imageId = req.body.imageId || req.body.image_id;
    const file = req.file;

    if (!userId || !imageId || !file) {
      return res.status(400).json({ message: "缺少 imageId 或模型檔" });
    }

    const base = await getBaseNameByImageId(imageId);

    const rawName = (file.originalname || "").toLowerCase();
    const ext = rawName.split(".").pop() || "";
    if (ext !== "fbx") {
      return res.status(400).json({ message: "模型檔必須是 .fbx 格式" });
    }

    await pool.query(`DELETE FROM char_model WHERE image_id=$1`, [imageId]);

    const key = `uploads/${base}.fbx`;
    const fileUrl = await uploadBufferToS3({
      buffer: file.buffer,
      key,
      contentType: "application/octet-stream",
    });

    await pool.query(
      `INSERT INTO char_model (image_id, file_path) VALUES ($1,$2)`,
      [imageId, fileUrl]
    );

    return res.json({ message: "模型已上傳（僅 .fbx）", file_path: fileUrl });
  } catch (err) {
    console.error("uploadModel error:", err);
    return res.status(500).json({ message: "模型上傳失敗", error: err.message });
  }
};

// 伺服器端代理下載
exports.proxyDownload = async (req, res) => {
  const { url, filename } = req.query;
  if (!url || !filename) {
    return res.status(400).json({ message: "缺少參數 url 或 filename" });
  }

  let target;
  try {
    target = new URL(url);
  } catch {
    return res.status(400).json({ message: "url 非法" });
  }

  const MAX_REDIRECTS = 3;
  const visited = new Set();

  function fetchOnce(currentUrl, redirects = 0) {
    if (redirects > MAX_REDIRECTS) {
      return res.status(508).json({ message: "轉址次數過多" });
    }
    if (visited.has(currentUrl)) {
      return res.status(508).json({ message: "偵測到循環轉址" });
    }
    visited.add(currentUrl);

    const client = currentUrl.startsWith("https") ? https : http;
    const reqUpstream = client.get(currentUrl, (fileRes) => {
      if (
        [301, 302, 303, 307, 308].includes(fileRes.statusCode) &&
        fileRes.headers.location
      ) {
        const nextUrl = new URL(fileRes.headers.location, currentUrl).toString();
        fileRes.resume();
        return fetchOnce(nextUrl, redirects + 1);
      }

      if (fileRes.statusCode !== 200) {
        fileRes.resume();
        return res
          .status(fileRes.statusCode || 502)
          .json({ message: "遠端資源無法存取" });
      }

      setDownloadHeaders(
        res,
        filename,
        fileRes.headers["content-type"],
        fileRes.headers["content-length"]
      );

      fileRes.pipe(res);
    });

    reqUpstream.on("error", (err) => {
      console.error("代理下載錯誤：", err);
      if (!res.headersSent) {
        res.status(500).json({ message: "代理下載失敗" });
      } else {
        res.destroy(err);
      }
    });
  }

  try {
    fetchOnce(target.toString(), 0);
  } catch (error) {
    console.error("proxyDownload 錯誤：", error);
    res.status(500).json({ message: "伺服器錯誤" });
  }
};

// 下載描述用資訊
exports.download = async (req, res) => {
  const { fileName } = req.query;

  if (!req.user_id) {
    return res.status(401).json({ message: "未授權存取" });
  }
  if (!fileName) {
    return res.status(400).json({ message: "請提供角色名稱（含副檔名）" });
  }

  try {
    const result = await pool.query(`
      SELECT i.file_name,
             i.file_path AS image_path,
             p.file_path AS profile_path,
             m.file_path AS memory_path,
             v.file_path AS voice_path
      FROM char_images i
      LEFT JOIN char_profile p ON i.id = p.image_id
      LEFT JOIN char_memory  m ON i.id = m.image_id
      LEFT JOIN char_voice   v ON i.id = v.image_id
      WHERE i.file_name = $1
        AND i.role_type = 'main'
    `, [fileName]);

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "查無對應角色主圖" });
    }

    const character = result.rows[0];
    return res.status(200).json({
      message: "下載成功",
      data: {
        filename: character.file_name,
        imagePath: character.image_path,
        profilePath: character.profile_path,
        memoryPath: character.memory_path,
        voicePath: character.voice_path,
      },
    });
  } catch (error) {
    console.error("下載錯誤：", error);
    return res.status(500).json({ message: "伺服器錯誤" });
  }
};

// 圖片分割上傳（head/body）
exports.splitCharacter = async (req, res) => {
  try {
    const { head, body, main } = req.files;
    const rawName = req.body.filename?.trim() || `char_${uuidv4()}`;
    const userId = req.user_id;

    let safeBase = toSafeBaseName(rawName);
    if (!/[\w\u4e00-\u9fa5-]/.test(safeBase) || safeBase === "file") {
      safeBase = `char_${uuidv4()}`;
    }

    if (!head || !body) {
      return res.status(400).json({ message: "缺少圖片檔案" });
    }

    const headFile = head[0];
    const bodyFile = body[0];
    const mainFile = main?.[0] || null;

    headFile.originalname = `${safeBase}_001.png`;
    bodyFile.originalname = `${safeBase}_002.png`;
    if (mainFile && !mainFile.originalname)
      mainFile.originalname = `${safeBase}.png`;

    let uploadBatch = req.body.upload_batch || req.body.uploadBatch || null;
    if (!uploadBatch) {
      const anyQ = await pool.query(`
        SELECT upload_batch FROM char_images
        WHERE user_id = $1
          AND (split_part(file_name,'.',1) = $2 OR split_part(file_name,'_',1) = $2)
        ORDER BY uploaded_at DESC
        LIMIT 1
      `, [userId, safeBase]);
      uploadBatch = anyQ.rowCount ? anyQ.rows[0].upload_batch : uuidv4();
    }

    const uploadAndSave = async (file, roleType) => {
      const ext = ".png";
      let suffix = "000";
      if (roleType === "head") suffix = "001";
      else if (roleType === "body") suffix = "002";
      else if (roleType === "main") suffix = "000";

      const newFileName = await getUniqueFileNameFromDB(
        suffix === "000" ? safeBase : `${safeBase}_${suffix}`,
        ext
      );
      const key = `uploads/${newFileName}`;

      const fileUrl = await uploadBufferToS3({
        buffer: file.buffer,
        key,
        contentType: file.mimetype || "image/png",
      });

      const ins = await pool.query(
        `INSERT INTO char_images (user_id, file_name, file_path, upload_batch, role_type)
         VALUES ($1, $2, $3, $4, $5) RETURNING id`,
        [userId, newFileName, fileUrl, uploadBatch, roleType]
      );
      return {
        id: ins.rows[0].id,
        fileName: newFileName,
        filePath: fileUrl,
        roleType,
      };
    };

    const savedHead = await uploadAndSave(headFile, "head");
    const savedBody = await uploadAndSave(bodyFile, "body");

    let savedMain = null;
    if (mainFile) {
      savedMain = await uploadAndSave(mainFile, "main");
    } else {
      savedMain = await uploadAndSave(bodyFile, "main");
    }

    return res.json({
      message: "分割圖片上傳成功",
      head: savedHead,
      body: savedBody,
      main: savedMain,
      upload_batch: uploadBatch,
    });
  } catch (error) {
    console.error(" splitCharacter error:", error);
    return res
      .status(500)
      .json({ message: "分割上傳失敗", error: error.message });
  }
};

// 舊的一次性上傳接口（圖片＋描述＋語音），暫時保留
exports.upload = async (req, res) => {
  try {
    const { profile, memory, filename } = req.body;
    const user_id = req.user_id;
    const files = req.files?.file || [];
    const voice = req.files?.voice?.[0] || null;

    if (!user_id) return res.status(401).json({ message: "未授權存取" });
    if (!files.length || profile == null || memory == null || !filename) {
      return res.status(400).json({ message: "缺少必要資料" });
    }

    const cleanName = String(filename).replace(/[<>:"/\\|?*]+/g, "");

    let upload_batch = req.body.uploadBatch || req.body.upload_batch || null;

    if (!upload_batch) {
      const q = await pool.query(`
        SELECT upload_batch
        FROM char_images
        WHERE user_id = $1
          AND (split_part(file_name, '.', 1) = $2 OR split_part(file_name, '_', 1) = $2)
        ORDER BY uploaded_at DESC
        LIMIT 1
      `, [user_id, cleanName]);
      upload_batch = q.rowCount ? q.rows[0].upload_batch : uuidv4();
    }

    let mainImageId = null;
    let mainImagePath = null;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext =
        path.extname(file.originalname || "").toLowerCase() || ".png";

      const isHead = /_head(\.[a-z0-9]+)?$/i.test(file.originalname || "");
      const isBody = /_body(\.[a-z0-9]+)?$/i.test(file.originalname || "");
      const isFull = !isHead && !isBody;

      const roleType = isHead
        ? "head"
        : isBody
          ? "body"
          : mainImageId
            ? "gallery"
            : "main";

      const base =
        toSafeBaseName(cleanName) + (isHead ? "_head" : isBody ? "_body" : "");
      const uniqueName = await getUniqueFileNameFromDB(base, ext);
      const s3Key = `uploads/${uniqueName}`;

      const buffer =
        file.buffer || (file.path ? await fs.readFile(file.path) : null);
      if (!buffer) {
        return res.status(400).json({ message: "檔案內容為空" });
      }

      const finalPath =
        MODE === "s3"
          ? await uploadBufferToS3({
            buffer,
            key: s3Key,
            contentType: file.mimetype || "application/octet-stream",
          })
          : (await fs.rename(file.path, path.join(uploadDir, uniqueName)),
            `/uploads/${uniqueName}`);

      const imgResult = await pool.query(
        `INSERT INTO char_images (user_id, file_name, file_path, upload_batch, role_type) VALUES ($1, $2, $3, $4, $5) RETURNING id`,
        [user_id, uniqueName, finalPath, upload_batch, roleType]
      );

      const imageId = imgResult.rows[0].id;
      if (isFull && !mainImageId) {
        mainImageId = imageId;
        mainImagePath = finalPath;
      }
    }

    const saveJsonFile = async (type, content) => {
      const json = { type, content };
      const fileName = await getUniqueFileNameFromDB(
        `${toSafeBaseName(cleanName)}_${type}`,
        ".json"
      );
      const buffer = Buffer.from(JSON.stringify(json, null, 2));
      const key = `uploads/${fileName}`;

      return MODE === "s3"
        ? await uploadBufferToS3({
          buffer,
          key,
          contentType: "application/json",
        })
        : (await fs.writeFile(path.join(uploadDir, fileName), buffer),
          `/uploads/${fileName}`);
    };

    const profilePath = await saveJsonFile("profile", profile);
    const memoryPath = await saveJsonFile("memory", memory);

    await pool.query(
      `INSERT INTO char_profile (image_id, file_path) VALUES ($1, $2)`,
      [mainImageId, profilePath]
    );
    await pool.query(
      `INSERT INTO char_memory (image_id, file_path) VALUES ($1, $2)`,
      [mainImageId, memoryPath]
    );

    if (voice) {
      const voiceExt =
        path.extname(voice.originalname || "").toLowerCase() || ".wav";
      const voiceFileName = await getUniqueFileNameFromDB(
        `${toSafeBaseName(cleanName)}_voice`,
        voiceExt
      );
      const voiceBuffer =
        voice.buffer || (voice.path ? await fs.readFile(voice.path) : null);
      if (voiceBuffer) {
        const voiceKey = `uploads/${voiceFileName}`;
        const voicePath =
          MODE === "s3"
            ? await uploadBufferToS3({
              buffer: voiceBuffer,
              key: voiceKey,
              contentType: voice.mimetype || "audio/wav",
            })
            : (await fs.rename(
              voice.path,
              path.join(uploadDir, voiceFileName)
            ),
              `/uploads/${voiceFileName}`);

        await pool.query(
          `INSERT INTO char_voice (image_id, file_path) VALUES ($1, $2)`,
          [mainImageId, voicePath]
        );
      }
    }

    res.status(200).json({
      message: "上傳成功（舊流程）",
      data: {
        filename: toSafeBaseName(cleanName),
        imagePath: mainImagePath,
        profilePath,
        memoryPath,
        uploadBatch: req.body.uploadBatch || req.body.upload_batch,
      },
    });
  } catch (error) {
    console.error(" 上傳錯誤：", error);
    res.status(500).json({ message: "伺服器錯誤" });
  }
};

// 取得尚未處理為 .fbx 的主圖片清單
exports.getPendingImages = async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT ci.id,
             ci.file_name,
             ci.file_path,
             ci.upload_batch
      FROM char_images ci
      WHERE ci.role_type IN ('head', 'body')
        AND ci.upload_batch IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM char_model cm
          WHERE cm.image_id IN (
            SELECT id FROM char_images
            WHERE upload_batch = ci.upload_batch
          )
        )
      ORDER BY ci.upload_batch, ci.uploaded_at ASC
    `);

    res.status(200).json(result.rows);
  } catch (err) {
    console.error(" getPendingImages error:", err);
    res.status(500).json({ message: "伺服器錯誤" });
  }
};

// 下載語音檔（wav）
exports.downloadVoice = async (req, res) => {
  const { imageId, voiceUrl } = req.body;

  try {
    let finalVoiceUrl = voiceUrl;

    if (!finalVoiceUrl && imageId) {
      const result = await pool.query(`
        SELECT v.file_path
        FROM char_voice v
        WHERE v.image_id = $1
        ORDER BY v.id DESC
        LIMIT 1
      `, [imageId]);

      if (result.rowCount > 0) {
        finalVoiceUrl = result.rows[0].file_path;
      } else {
        return res.status(404).json({ message: "找不到對應的語音檔" });
      }
    }

    if (!finalVoiceUrl) {
      return res.status(400).json({ message: "缺少有效的 voice 路徑資訊" });
    }

    const args = ["scripts/download_voice.py", "--url", finalVoiceUrl];
    const pythonProcess = spawn("python", args, {
      cwd: process.cwd(),
    });

    let stdout = "", stderr = "";
    pythonProcess.stdout.on("data", data => { stdout += data.toString(); });
    pythonProcess.stderr.on("data", data => { stderr += data.toString(); });

    pythonProcess.on("close", code => {
      if (code === 0) {
        res.json({ message: "下載成功", output: stdout });
      } else {
        res.status(500).json({ message: "下載失敗", error: stderr });
      }
    });

  } catch (err) {
    console.error("downloadVoice error:", err);
    res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};

// 下載模型檔（fbx）
exports.downloadModel = async (req, res) => {
  const { fileName } = req.body;

  if (!fileName) {
    return res.status(400).json({ message: "缺少 fileName 參數" });
  }

  try {
    const args = ["scripts/download_model.py", "--file-name", fileName];
    const pythonProcess = spawn("python", args, {
      cwd: process.cwd(),
    });

    let stdout = "", stderr = "";
    pythonProcess.stdout.on("data", data => { stdout += data.toString(); });
    pythonProcess.stderr.on("data", data => { stderr += data.toString(); });

    pythonProcess.on("close", code => {
      if (code === 0) {
        res.json({ message: "模型下載成功", output: stdout });
      } else {
        res.status(500).json({ message: "模型下載失敗", error: stderr });
      }
    });

  } catch (err) {
    console.error("downloadModel error:", err);
    res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};

// 下載關鍵人物資訊（json）
exports.downloadProfile = async (req, res) => {
  const { fileName } = req.body;

  if (!fileName) {
    return res.status(400).json({ message: "缺少 fileName 參數" });
  }

  try {
    const args = ["scripts/download_profile.py", "--file-name", fileName];
    const pythonProcess = spawn("python", args, {
      cwd: process.cwd(),
    });

    let stdout = "", stderr = "";
    pythonProcess.stdout.on("data", data => { stdout += data.toString(); });
    pythonProcess.stderr.on("data", data => { stderr += data.toString(); });

    pythonProcess.on("close", code => {
      if (code === 0) {
        res.json({ message: "profile 下載成功", output: stdout });
      } else {
        res.status(500).json({ message: "profile 下載失敗", error: stderr });
      }
    });

  } catch (err) {
    console.error("downloadProfile error:", err);
    res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};

// 下載人物記憶描述（txt）
exports.downloadMemory = async (req, res) => {
  const { fileName } = req.body;

  if (!fileName) {
    return res.status(400).json({ message: "缺少 fileName 參數" });
  }

  try {
    const args = ["scripts/download_memory.py", "--file-name", fileName];
    const pythonProcess = spawn("python", args, {
      cwd: process.cwd(),
    });

    let stdout = "", stderr = "";
    pythonProcess.stdout.on("data", data => { stdout += data.toString(); });
    pythonProcess.stderr.on("data", data => { stderr += data.toString(); });

    pythonProcess.on("close", code => {
      if (code === 0) {
        res.json({ message: "記憶下載成功", output: stdout });
      } else {
        res.status(500).json({ message: "記憶下載失敗", error: stderr });
      }
    });

  } catch (err) {
    console.error("downloadMemory error:", err);
    res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};

// 寫入檔名
exports.writeIndex = async (req, res) => {
  const { fileName } = req.body;

  if (!fileName) {
    return res.status(400).json({ message: "缺少 fileName 參數" });
  }

  try {
    const args = ["scripts/write_index.py", "--file-name", fileName];
    const pythonProcess = spawn("python", args, {
      cwd: process.cwd()
    });

    let stdout = "", stderr = "";
    pythonProcess.stdout.on("data", data => { stdout += data.toString(); });
    pythonProcess.stderr.on("data", data => { stderr += data.toString(); });

    pythonProcess.on("close", code => {
      if (code === 0) {
        res.json({ message: "index.txt 寫入成功", output: stdout });
      } else {
        res.status(500).json({ message: "index.txt 寫入失敗", error: stderr });
      }
    });

  } catch (err) {
    console.error("writeIndex error:", err);
    res.status(500).json({ message: "伺服器錯誤", error: err.message });
  }
};