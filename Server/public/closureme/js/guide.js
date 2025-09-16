// guide.js
function initGuideModal() {
  const titles = [
    "系統介紹",
    "操作說明 1/3",
    "操作說明 2/3",
    "操作說明 3/3"
  ];

  const texts = [
    "歡迎使用 ClosureMe！",
    "無內容",
    "無內容",
    "無內容"
  ];

  let pageIndex = 0;

  const titleEl = document.getElementById("guide-title");
  const textEl = document.getElementById("guide-text");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");

  function updatePage() {
    titleEl.textContent = titles[pageIndex];
    textEl.textContent = texts[pageIndex];

    prevBtn.style.display = pageIndex === 0 ? "none" : "inline-block";
    nextBtn.style.display = pageIndex === titles.length - 1 ? "none" : "inline-block";
  }

  prevBtn.onclick = () => {
    if (pageIndex > 0) {
      pageIndex--;
      updatePage();
    }
  };

  nextBtn.onclick = () => {
    if (pageIndex < titles.length - 1) {
      pageIndex++;
      updatePage();
    }
  };

  updatePage();
}