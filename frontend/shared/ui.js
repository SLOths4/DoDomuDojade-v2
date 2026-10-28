import { ApiError, api, setApiLocale } from "/shared/api.js";
import { loadMessages, saveLocale } from "/shared/i18n.js";

const TOAST_MS = 4000;

// Maps a validation error type from the API to a message, using the form's field limits.
export function fieldMessage(t, type, limits = {}) {
  switch (type) {
    case "missing":
      return t("validation.required");
    case "string_too_short":
      return limits.min ? t("validation.too_short", { min: limits.min }) : t("validation.required");
    case "string_too_long":
      return t("validation.too_long", { max: limits.max });
    case "date_from_datetime_parsing":
    case "date_parsing":
    case "datetime_from_date_parsing":
    case "datetime_parsing":
    case "timezone_aware":
      return t("validation.invalid_date");
    default:
      return t("validation.invalid");
  }
}

// A reusable form: keeps entered values on error and exposes per-field messages.
export function formMixin() {
  return {
    errors: {},
    formError: "",
    busy: false,

    async submit(action, { limits = {}, onSuccess } = {}) {
      this.errors = {};
      this.formError = "";
      this.busy = true;
      const session = window.Alpine.store("session");
      const t = (key, params) => session.t(key, params);
      try {
        const result = await action();
        onSuccess?.(result);
        return result;
      } catch (error) {
        if (error instanceof ApiError && Object.keys(error.fields).length) {
          for (const [field, type] of Object.entries(error.fields)) {
            this.errors[field] = fieldMessage(t, type, limits[field]);
          }
        } else if (error instanceof ApiError && error.message) {
          this.formError = error.message;
        } else {
          this.formError = t(error?.code === "NETWORK_ERROR" ? "errors.network" : "errors.unexpected");
        }
        return undefined;
      } finally {
        this.busy = false;
      }
    },
  };
}

export function registerUi(Alpine) {
  Alpine.store("session", {
    user: null,
    config: null,
    locale: "pl",
    messages: {},
    ready: false,

    t(key, params = {}) {
      const template = this.messages[key] ?? key;
      return template.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`);
    },

    async init() {
      await this.useLocale();
      this.config = await api("/config");
      this.ready = true;
    },

    async useLocale(locale) {
      const loaded = await loadMessages(locale);
      this.messages = loaded.messages;
      this.locale = loaded.locale;
      setApiLocale(this.locale);
    },

    async changeLocale(locale) {
      saveLocale(locale);
      await this.useLocale(locale);
      if (this.user) {
        this.user = await api("/auth/me", { method: "PATCH", body: { locale } });
      }
    },

    formatDate(value) {
      if (!value) return "—";
      return new Date(value).toLocaleDateString(this.locale === "pl" ? "pl-PL" : "en-GB");
    },

    formatDateTime(value) {
      if (!value) return "—";
      return new Date(value).toLocaleString(this.locale === "pl" ? "pl-PL" : "en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      });
    },
  });

  Alpine.store("ui", {
    toasts: [],
    confirmation: null,

    toast(message, kind = "success") {
      const id = Math.random().toString(36).slice(2);
      this.toasts.push({ id, message, kind });
      setTimeout(() => {
        this.toasts = this.toasts.filter((toast) => toast.id !== id);
      }, TOAST_MS);
    },

    error(error) {
      const t = (key) => Alpine.store("session").t(key);
      const message =
        error instanceof ApiError && error.message
          ? error.message
          : error?.code === "NETWORK_ERROR"
            ? t("errors.network")
            : t("errors.unexpected");
      this.toast(message, "error");
    },

    confirm(message, actionLabel) {
      return new Promise((resolve) => {
        this.confirmation = { message, actionLabel, resolve };
      });
    },

    answer(value) {
      this.confirmation?.resolve(value);
      this.confirmation = null;
    },
  });

  Alpine.data("form", formMixin);
}

export function toLocalInput(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fromLocalInput(value) {
  return value ? new Date(value).toISOString() : null;
}
