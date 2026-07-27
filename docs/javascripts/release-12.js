(() => {
  const boot = () => {
    document.querySelectorAll("[data-release12-explorer]").forEach((root) => {
      if (root.dataset.ready === "true") return;
      root.dataset.ready = "true";

      const tabs = Array.from(root.querySelectorAll("[data-release12-tab]"));
      const panels = Array.from(root.querySelectorAll("[data-release12-panel]"));

      const select = (name, focus = false) => {
        tabs.forEach((tab) => {
          const active = tab.dataset.release12Tab === name;
          tab.setAttribute("aria-selected", String(active));
          tab.tabIndex = active ? 0 : -1;
          if (active && focus) tab.focus();
        });
        panels.forEach((panel) => {
          panel.hidden = panel.dataset.release12Panel !== name;
        });
      };

      tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => select(tab.dataset.release12Tab));
        tab.addEventListener("keydown", (event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          let next = index;
          if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
          if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
          if (event.key === "Home") next = 0;
          if (event.key === "End") next = tabs.length - 1;
          select(tabs[next].dataset.release12Tab, true);
        });
      });

      const initial = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
      if (initial) select(initial.dataset.release12Tab);
    });
  };

  if (typeof document$ !== "undefined") {
    document$.subscribe(boot);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
