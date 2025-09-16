// auth.js
export function getToken() {
    return localStorage.getItem("token");
}

export function checkToken() {
    const token = getToken();
    if (!token) {
        redirectToLogin("請先登入");
        return false;
    }

    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const now = Math.floor(Date.now() / 1000);
        if (payload.exp && payload.exp < now) {
            redirectToLogin("登入已過期，請重新登入");
            return false;
        }
    } catch (e) {
        console.error("Token 驗證解析錯誤:", e);
        redirectToLogin("驗證失敗，請重新登入");
        return false;
    }
    return true;
}

export function redirectToLogin(message) {
    localStorage.clear();
    if (message) {
        showToast(message, "error");
    }
    setTimeout(() => {
        window.location.href = "/auth/html/login.html";
    }, 800);
}

export function logout() {
    localStorage.clear();
    window.location.href = "/auth/html/login.html";
}

export async function handleApiResponse(res) {
    if (res.status === 401 || res.status === 403) {
        redirectToLogin("登入已過期或未授權，請重新登入");
        return null;
    }
    try {
        return await res.json();
    } catch (e) {
        console.error("API 回應解析失敗:", e);
        return null;
    }
}