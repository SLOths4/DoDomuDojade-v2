const SUPPORTED = ["pl", "en"];
const STORAGE_KEY = "ddd.locale";

function preferredLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (SUPPORTED.includes(saved)) return saved;
  } catch {
    // Storage can be unavailable (private mode); fall back to the browser language.
  }
  const browser = (navigator.language || "pl").slice(0, 2).toLowerCase();
  return SUPPORTED.includes(browser) ? browser : "pl";
}

export async function loadMessages(locale = preferredLocale()) {
  const response = await fetch(`/shared/locales/${locale}.json`);
  const messages = await response.json();
  document.documentElement.lang = locale;
  return {
    locale,
    t: (key, params = {}) =>
      (messages[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`),
  };
}

export function saveLocale(locale) {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // Not persisted; the choice still applies until the page reloads.
  }
}
