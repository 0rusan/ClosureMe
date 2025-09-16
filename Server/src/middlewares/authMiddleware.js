// token 驗證
const jwt = require("jsonwebtoken");

const authMiddleware = (req, res, next) => {
    const authHeader = req.headers["authorization"];
    if (!authHeader) {
        return res.status(401).json({ message: "未提供授權憑證" });
    }

    const parts = authHeader.split(" ");
    const scheme = parts[0];
    const token = parts[1];

    if (!token || !/^Bearer$/i.test(scheme)) {
        return res.status(401).json({ message: "授權格式錯誤，應為 Bearer <token>" });
    }

    jwt.verify(token, process.env.JWT_SECRET, (err, decoded) => {
        if (err) {
            return res.status(403).json({ message: "Token 無效或已過期" });
        }
        req.user_id = decoded.user_id;
        req.username = decoded.username;
        next();
    });
};

module.exports = authMiddleware;