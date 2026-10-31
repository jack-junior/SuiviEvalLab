// Screenshots open full size in a new tab.
document.addEventListener("click", (e) => {
  const img = e.target.closest(".md-typeset img");
  if (img) window.open(img.currentSrc || img.src, "_blank", "noopener");
});
