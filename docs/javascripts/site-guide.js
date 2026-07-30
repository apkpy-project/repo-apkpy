(function () {
  function initCapabilityFilter() {
    var controls = Array.prototype.slice.call(
      document.querySelectorAll("[data-capability-filter]")
    );
    var cards = Array.prototype.slice.call(
      document.querySelectorAll("[data-capabilities]")
    );
    var result = document.getElementById("capability-result");
    if (!controls.length || !cards.length) return;

    controls.forEach(function (control) {
      control.addEventListener("click", function () {
        var filter = control.getAttribute("data-capability-filter") || "all";
        var visible = 0;

        controls.forEach(function (item) {
          var active = item === control;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", active ? "true" : "false");
        });

        cards.forEach(function (card) {
          var capabilities = (card.getAttribute("data-capabilities") || "").split(/\s+/);
          var show = filter === "all" || capabilities.indexOf(filter) !== -1;
          card.hidden = !show;
          if (show) visible += 1;
        });

        if (result) {
          result.textContent =
            filter === "all"
              ? "Showing all " + visible + " app types."
              : "Showing " + visible + " app types for " + filter + ".";
        }
      });
    });

    controls.forEach(function (control, index) {
      control.setAttribute("aria-pressed", index === 0 ? "true" : "false");
    });
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(initCapabilityFilter);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCapabilityFilter);
  } else {
    initCapabilityFilter();
  }
})();
