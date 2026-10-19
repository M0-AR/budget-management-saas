(function () {
  try {
    var stored = localStorage.getItem("bms.theme") || "system";
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var dark = stored === "dark" || (stored === "system" && prefersDark);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    var branding = localStorage.getItem("bms.branding");
    if (branding) {
      var parsed = JSON.parse(branding);
      if (parsed && /^#[0-9a-fA-F]{6}$/.test(parsed.accent_color || "")) {
        document.documentElement.style.setProperty("--accent", parsed.accent_color);
      }
    }
  } catch (error) {
    /* first paint must never fail */
  }
})();
