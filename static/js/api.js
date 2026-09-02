let csrfToken = "";

export class APIError extends Error {
  constructor(response, payload) {
    super(payload?.error?.message || response.statusText || "Request failed");
    this.code = payload?.error?.code || "REQUEST_FAILED";
    this.status = response.status;
  }
}

export function setCSRF(token) { csrfToken = token || ""; }

export async function request(path, options={}, retry=true) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!/^(GET|HEAD)$/i.test(options.method || "GET") && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {credentials:"same-origin", ...options, headers, signal:controller.signal});
    const payload = response.headers.get("content-type")?.includes("json") ? await response.json() : null;
    if (!response.ok) {
      if (retry && response.status === 403 && payload?.error?.code === "CSRF_FAILED") {
        const fresh = await request("/api/csrf", {}, false);
        setCSRF(fresh.csrfToken);
        return request(path, options, false);
      }
      throw new APIError(response, payload);
    }
    return payload?.data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out");
    throw error;
  } finally { clearTimeout(timeout); }
}

export function upload(file, fields={}, onProgress=()=>{}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    Object.entries(fields).forEach(([key, value]) => form.append(key, String(value)));
    xhr.open("POST", "/api/media");
    xhr.responseType = "json";
    xhr.withCredentials = true;
    if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    xhr.onload = () => xhr.status >= 200 && xhr.status < 300
      ? resolve(xhr.response?.data)
      : reject(new Error(xhr.response?.error?.message || "Upload failed"));
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}
