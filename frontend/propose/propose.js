import { api } from "/shared/api.js";
import { formMixin, registerUi } from "/shared/ui.js";

document.addEventListener("alpine:init", () => {
  const Alpine = window.Alpine;
  registerUi(Alpine);
  const session = Alpine.store("session");

  Alpine.data("proposeForm", () => ({
    ...formMixin(),
    title: "",
    text: "",
    validUntil: "",
    sent: false,

    async init() {
      await session.init();
    },

    t(key, params) {
      return session.t(key, params);
    },

    get limits() {
      const c = session.config?.announcement ?? {};
      return {
        title: { min: c.titleMinLength, max: c.titleMaxLength },
        text: { min: c.textMinLength, max: c.textMaxLength },
      };
    },

    async send() {
      const body = { title: this.title, text: this.text, validUntil: this.validUntil || null };
      const created = await this.submit(
        () => api("/announcements/proposals", { method: "POST", body }),
        { limits: this.limits },
      );
      if (created) {
        this.title = this.text = this.validUntil = "";
        this.sent = true;
      }
    },
  }));
});
