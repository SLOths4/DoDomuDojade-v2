export class ApiError extends Error {
  constructor(code, message, status, context = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.context = context ?? {};
  }

  get fields() {
    return this.context.fields ?? {};
  }
}

let currentLocale = "pl";

export function setApiLocale(locale) {
  currentLocale = locale;
}

function csrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function api(path, { method = "GET", body, query } = {}) {
  const headers = { Accept: "application/json", "Accept-Language": currentLocale };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const search = query ? `?${new URLSearchParams(query)}` : "";

  let response;
  try {
    response = await fetch(`/api${path}${search}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "", 0);
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = data?.data ?? {};
    if (response.status === 401) window.dispatchEvent(new CustomEvent("ddd:unauthenticated"));
    throw new ApiError(error.code ?? "HTTP_ERROR", data?.message ?? "", response.status, error.context);
  }
  return data;
}
