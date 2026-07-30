(() => {
  const initial = [
    { id: "post-1", author: "Mira Vale", message: "Like this record, then settle the request.", time: "2m", badge: "128 LIKES" },
    { id: "post-2", author: "Eli Brooks", message: "Delete this record and restore it after failure.", time: "6m", badge: "BUILD LOG" },
    { id: "post-3", author: "Noor Kim", message: "A live batch can patch this record in place.", time: "11m", badge: "ENGINEERING" }
  ];

  const clone = (value) => JSON.parse(JSON.stringify(value));

  const boot = () => {
    document.querySelectorAll("[data-feed-lab]").forEach((root) => {
      if (root.dataset.ready === "true") return;
      root.dataset.ready = "true";

      const list = root.querySelector("[data-feed-list]");
      const status = root.querySelector("[data-feed-status]");
      let items = clone(initial);
      const snapshots = new Map();

      const setStatus = (message) => {
        status.textContent = message;
        status.classList.remove("feed-lab__flash");
        requestAnimationFrame(() => status.classList.add("feed-lab__flash"));
      };

      const render = (changed = "") => {
        list.replaceChildren(...items.map((item) => {
          const row = document.createElement("article");
          row.dataset.id = item.id;
          if (item.id === changed) row.classList.add("is-changed");

          const copy = document.createElement("div");
          const author = document.createElement("strong");
          const message = document.createElement("p");
          author.textContent = item.author;
          message.textContent = item.message;
          copy.append(author, message);

          const meta = document.createElement("div");
          const time = document.createElement("span");
          const badge = document.createElement("b");
          time.textContent = item.time;
          badge.textContent = item.badge;
          meta.append(time, badge);

          row.append(copy, meta);
          return row;
        }));
      };

      const find = (id) => items.findIndex((item) => item.id === id);
      const snapshot = (name) => {
        if (!snapshots.has(name)) snapshots.set(name, clone(items));
      };

      root.querySelectorAll("[data-feed-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const action = button.dataset.feedAction;

          if (action === "prepend") {
            items = items.filter((item) => item.id !== "post-live");
            items.unshift({ id: "post-live", author: "Rhea Stone", message: "A new record arrived above the current view.", time: "now", badge: "LIVE" });
            setStatus("Rhea prepended; existing records kept their order.");
            render("post-live");
          }

          if (action === "merge") {
            const noor = find("post-3");
            if (noor >= 0) items[noor] = { ...items[noor], message: "Updated in place from a live response.", time: "now", badge: "EDITED" };
            if (find("post-remote") < 0) items.push({ id: "post-remote", author: "Cal Ross", message: "An unseen ID was appended once.", time: "now", badge: "REMOTE" });
            setStatus("Noor updated in place; Cal appended without a duplicate.");
            render("post-3");
          }

          if (action === "like") {
            const index = find("post-1");
            if (index >= 0) {
              snapshot("like-post-1");
              items[index] = { ...items[index], time: "now", badge: "129 LIKES" };
            }
            setStatus("Mira changed immediately; like-post-1 is pending.");
            render("post-1");
          }

          if (action === "commit") {
            snapshots.delete("like-post-1");
            setStatus("Like accepted. The row stays at 129; only its snapshot was discarded.");
            render();
          }

          if (action === "delete") {
            const index = find("post-2");
            if (index >= 0) {
              snapshot("delete-post-2");
              items.splice(index, 1);
            }
            setStatus("Eli removed locally; delete-post-2 can still be restored.");
            render();
          }

          if (action === "rollback") {
            if (snapshots.has("delete-post-2")) {
              items = snapshots.get("delete-post-2");
              snapshots.delete("delete-post-2");
              setStatus("Rollback restored Eli and the previous dataset.");
              render("post-2");
            } else {
              setStatus("Nothing to restore. Delete Eli first.");
            }
          }

          if (action === "reset") {
            items = clone(initial);
            snapshots.clear();
            setStatus("Demo reset. All rows and snapshots returned to their initial state.");
            render();
          }
        });
      });

      render();
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
