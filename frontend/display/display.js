import { api } from "/shared/api.js";

const HEALTH_INTERVAL_MS = 30_000;

document.addEventListener("alpine:init", () => {
  window.Alpine.data("displayShell", () => ({
    time: "",
    date: "",
    apiOk: false,

    init() {
      this.tick();
      setInterval(() => this.tick(), 1000);
      this.checkApi();
      setInterval(() => this.checkApi(), HEALTH_INTERVAL_MS);
    },

    tick() {
      const now = new Date();
      this.time = now.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
      this.date = now.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
    },

    async checkApi() {
      try {
        await api("/health");
        this.apiOk = true;
      } catch {
        this.apiOk = false;
      }
    },
  }));
});
