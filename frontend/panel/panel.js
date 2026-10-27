import { api } from "/shared/api.js";
import { loadMessages, saveLocale } from "/shared/i18n.js";

const i18nReady = loadMessages();

document.addEventListener("alpine:init", () => {
  window.Alpine.data("panelShell", () => ({
    locale: "pl",
    apiOk: false,
    translate: (key) => key,

    async init() {
      await this.applyMessages(i18nReady);
      try {
        await api("/health");
        this.apiOk = true;
      } catch {
        this.apiOk = false;
      }
    },

    t(key, params) {
      return this.translate(key, params);
    },

    async applyMessages(messagesPromise) {
      const { locale, t } = await messagesPromise;
      this.locale = locale;
      this.translate = t;
    },

    async switchLocale() {
      saveLocale(this.locale);
      await this.applyMessages(loadMessages(this.locale));
    },
  }));
});
