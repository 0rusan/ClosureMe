// 彈窗設定
function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    if (!toast) return;

    toast.textContent = message;
    toast.style.backgroundColor =
        type === "success" ? "#28a745" :
            type === "error" ? "#dc3545" :
                type === "info" ? "#17a2b8" :
                    "#333";

    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2000);
}
window.showToast = showToast;