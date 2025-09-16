// login.js
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("loginBtn")?.addEventListener("click", login);
});

async function login() {
    const identifier = (document.getElementById("loginIdentifier")?.value || "").trim();
    const password = (document.getElementById("loginPassword")?.value || "").trim();

    if (!identifier || !password) {
        showToast("請輸入帳號/信箱與密碼", "error");
        return;
    }

    try {
        const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ identifier, password }),
        });

        const data = await res.json().catch(() => ({ message: "登入失敗" }));

        if (res.ok && data.token) {
            localStorage.setItem("token", data.token);
            const username = data?.user?.username || identifier;
            localStorage.setItem("username", username);

            const urlParams = new URLSearchParams(location.search);
            const urlRedirect = (urlParams.get("redirect") || "").trim();
            const lsRedirect = (localStorage.getItem("postLoginRedirect") || "").trim();
            const back = lsRedirect || urlRedirect || "/";

            try { localStorage.removeItem("postLoginRedirect"); } catch { }

            showToast("登入成功，正在返回首頁", "success");
            setTimeout(() => { location.replace(back); }, 1000);

        } else {
            handleLoginError(data.message);
        }
    } catch (err) {
        console.error("無法連線伺服器：", err);
        showToast("無法連線伺服器，請檢查網路或稍後再試", "error");
    }
}

function handleLoginError(message) {
    switch (message) {
        case "缺少帳號或密碼":
            showToast("請輸入帳號/信箱與密碼", "error");
            break;
        case "帳號不存在":
            showToast("查無此帳號，請確認輸入或前往註冊", "error");
            break;
        case "密碼錯誤":
            showToast("密碼錯誤，請再試一次", "error");
            const pwd = document.getElementById("loginPassword");
            if (pwd) pwd.value = "";
            break;
        default:
            showToast(message || "登入失敗", "error");
    }
}