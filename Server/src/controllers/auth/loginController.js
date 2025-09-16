// loginController.js
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const pool = require("../../models/db");

exports.login = async (req, res) => {
    const { identifier, password } = req.body;

    if (!identifier || !password) {
        return res.status(400).json({ message: "缺少帳號或密碼" });
    }

    try {
        const result = await pool.query(
            "SELECT * FROM users WHERE username = $1 OR email = $1",
            [identifier]
        );

        if (result.rows.length === 0) {
            return res.status(401).json({ message: "帳號不存在" });
        }

        const user = result.rows[0];
        const match = await bcrypt.compare(password, user.password);
        if (!match) {
            return res.status(401).json({ message: "密碼錯誤" });
        }

        const token = jwt.sign(
            { user_id: user.id, username: user.username },
            process.env.JWT_SECRET,
            { expiresIn: process.env.JWT_EXPIRES || "1h" }
        );

        res.json({
            message: "登入成功",
            token,
            user: {
                id: user.id,
                username: user.username,
                email: user.email
            }
        });

    } catch (error) {
        console.error("Login Error:", error);
        res.status(500).json({ message: "伺服器錯誤" });
    }
};