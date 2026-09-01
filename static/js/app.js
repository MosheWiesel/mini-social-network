"use strict";

// ---------- Configuration and state ----------

const CONFIG = Object.freeze({
  productName: "Circa",
  storage: {
    userID: "circa-user-id",
    username: "circa-username",
    language: "circa-language",
    theme: "circa-theme"
  },
  requestTimeout: 12000,
  toastDuration: 4200
});

const state = {
  language: localStorage.getItem(CONFIG.storage.language) || "he",
  theme: localStorage.getItem(CONFIG.storage.theme) || null,
  userID: Number(localStorage.getItem(CONFIG.storage.userID)) || null,
  username: localStorage.getItem(CONFIG.storage.username) || "",
  authMode: "login",
  activeView: "feed",
  users: [],
  userMap: new Map(),
  posts: [],
  requests: [],
  feedStatus: "idle",
  usersStatus: "idle",
  requestsStatus: "idle",
  sentRequests: new Set(),
  replyTargets: new Map(),
  deletePostID: null,
  lastModalFocus: null
};

const translations = {
  he: {
    eyebrow: "המקום לאנשים שלך", welcome: "טוב לראות אותך", tagline: "שיחות אמיתיות, בקצב שנעים לך.",
    login: "כניסה", signup: "הרשמה", username: "שם משתמש", password: "סיסמה",
    usernamePlaceholder: "למשל, noa", passwordPlaceholder: "הסיסמה שלך", loginButton: "כניסה לחשבון",
    signupButton: "יצירת חשבון", authFootnote: "הסיסמה נשלחת רק לשרת הפרויקט ואינה נשמרת בדפדפן.",
    showPassword: "הצגת סיסמה", hidePassword: "הסתרת סיסמה", toggleTheme: "החלפת מצב תצוגה", switchLanguage: "החלפת שפה",
    authentication: "כניסה והרשמה", primaryNavigation: "ניווט ראשי", mobileNavigation: "ניווט למובייל",
    home: "בית", people: "אנשים", requests: "בקשות", profile: "הפרופיל שלי", profileShort: "פרופיל", settings: "הגדרות",
    logout: "יציאה", yourCircle: "המעגל שלך", createPost: "יצירת פוסט", composerPlaceholder: "מה עובר לך בראש?",
    publish: "פרסום", discover: "לגלות ולהתחבר", searchPeople: "חיפוש אנשים", connections: "חיבורים שמחכים לך",
    yourSpace: "המקום שלך", simpleProfile: "פשוט ואמיתי", profileLimit: "הפרופיל מציג רק מידע שקיים במערכת.",
    makeItYours: "להרגיש בבית", language: "שפה", languageDescription: "בחרו את שפת הממשק",
    appearance: "מראה", appearanceDescription: "מצב בהיר או כהה", logoutDescription: "ניתן להיכנס שוב בכל עת",
    lightMode: "מצב בהיר", darkMode: "מצב כהה", peopleWaiting: "אנשים שמחכים", viewAll: "הכול",
    smallCircle: "מעגל קטן. שיחות גדולות.", smallCircleCopy: "כאן רואים רק תוכן אמיתי מהאנשים המחוברים אליך.",
    refresh: "רענון", close: "סגירה", delete: "מחיקה", cancel: "ביטול", deletePost: "מחיקת פוסט",
    deletePostTitle: "למחוק את הפוסט?", deletePostDescription: "הפעולה תמחק גם את כל התגובות ולא ניתן לבטל אותה.",
    requiredUsername: "יש להזין שם משתמש.", requiredPassword: "יש להזין סיסמה.", submitting: "רק רגע…",
    loginSuccess: "נכנסת בהצלחה. טוב לראות אותך!", signupSuccess: "החשבון נוצר. עכשיו אפשר להיכנס.",
    genericError: "משהו לא הסתדר. אפשר לנסות שוב.", networkError: "לא ניתן להתחבר לשרת. ודאו ש־Flask פועל ונסו שוב.",
    timeoutError: "השרת לא הגיב בזמן. נסו שוב בעוד רגע.", invalidCredentials: "שם המשתמש או הסיסמה אינם נכונים.",
    usernameExists: "שם המשתמש כבר קיים.", missingCredentials: "יש להזין שם משתמש וסיסמה.",
    loadingFeed: "טוען את המעגל שלך", feedEmptyTitle: "עוד שקט כאן", feedEmptyCopy: "פוסטים של החברים המחוברים אליך יופיעו כאן.",
    feedErrorTitle: "לא הצלחנו לטעון את הפיד", feedErrorCopy: "המידע לא זמין כרגע. אפשר לנסות שוב.", retry: "ניסיון נוסף",
    postCreated: "הפוסט פורסם בהצלחה.", postDeleted: "הפוסט נמחק.", postCreateError: "לא הצלחנו לפרסם את הפוסט.",
    comments: "תגובות", noComments: "עוד אין תגובות. אפשר להתחיל את השיחה.", commentPlaceholder: "כתיבת תגובה…",
    reply: "תגובה", replyingTo: "תגובה ל־{name}", cancelReply: "ביטול תגובה", commentAdded: "התגובה נוספה.",
    commentError: "לא הצלחנו להוסיף את התגובה.", deleteError: "לא הצלחנו למחוק את הפוסט.", unknownUser: "משתמש לא מוכר",
    userNumber: "משתמש #{id}", sendRequest: "שליחת בקשה", sending: "שולח…", requestSent: "הבקשה נשלחה",
    requestSentToast: "בקשת החברות נשלחה.", requestError: "לא הצלחנו לשלוח את הבקשה.",
    peopleEmptyTitle: "אין אנשים נוספים", peopleEmptyCopy: "כאשר משתמשים נוספים יצטרפו, הם יופיעו כאן.",
    noResultsTitle: "לא מצאנו התאמה", noResultsCopy: "נסו שם אחר או נקו את החיפוש.",
    peopleErrorTitle: "לא הצלחנו לטעון אנשים", peopleErrorCopy: "רשימת המשתמשים אינה זמינה כרגע.",
    requestsEmptyTitle: "אין בקשות ממתינות", requestsEmptyCopy: "כשתגיע בקשה חדשה, היא תופיע כאן.",
    requestsErrorTitle: "לא הצלחנו לטעון בקשות", requestsErrorCopy: "הבקשות אינן זמינות כרגע.",
    pendingRequest: "שלח/ה לך בקשת חברות", pendingOnly: "ממתינה לאישור", approve: "אישור", reject: "דחייה",
    requestApproved: "בקשת החברות אושרה.", requestRejected: "בקשת החברות נדחתה.", requestHandleError: "לא הצלחנו לעדכן את הבקשה.",
    noPreviewRequests: "אין בקשות חדשות כרגע.", loggedOut: "יצאת מהחשבון.", sessionRestored: "החשבון שוחזר.",
    unauthorized: "הגישה נדחתה. נסו לצאת ולהיכנס שוב.", alreadyRequested: "כבר קיימת בקשה או שהפעולה אינה אפשרית.",
    postNotFound: "הפוסט לא נמצא.", invalidPost: "מזהה הפוסט אינו תקין.", writeSomething: "יש לכתוב תוכן לפני הפרסום.",
    welcomeBack: "שלום, {name}", loading: "טוען…"
  },
  en: {
    eyebrow: "A place for your people", welcome: "Good to see you", tagline: "Real conversations, at your own pace.",
    login: "Log in", signup: "Sign up", username: "Username", password: "Password",
    usernamePlaceholder: "For example, noa", passwordPlaceholder: "Your password", loginButton: "Log in to your account",
    signupButton: "Create account", authFootnote: "Your password is sent only to the project server and is never stored in the browser.",
    showPassword: "Show password", hidePassword: "Hide password", toggleTheme: "Toggle display mode", switchLanguage: "Switch language",
    authentication: "Log in and sign up", primaryNavigation: "Primary navigation", mobileNavigation: "Mobile navigation",
    home: "Home", people: "People", requests: "Requests", profile: "My profile", profileShort: "Profile", settings: "Settings",
    logout: "Log out", yourCircle: "Your circle", createPost: "Create post", composerPlaceholder: "What’s on your mind?",
    publish: "Publish", discover: "Discover and connect", searchPeople: "Search people", connections: "Connections waiting for you",
    yourSpace: "Your space", simpleProfile: "Simple and genuine", profileLimit: "This profile only shows information available in the system.",
    makeItYours: "Make it yours", language: "Language", languageDescription: "Choose the interface language",
    appearance: "Appearance", appearanceDescription: "Light or dark mode", logoutDescription: "You can log in again at any time",
    lightMode: "Light mode", darkMode: "Dark mode", peopleWaiting: "People waiting", viewAll: "View all",
    smallCircle: "A small circle. Bigger conversations.", smallCircleCopy: "See real posts from the people connected to you.",
    refresh: "Refresh", close: "Close", delete: "Delete", cancel: "Cancel", deletePost: "Delete post",
    deletePostTitle: "Delete this post?", deletePostDescription: "This will also delete every comment and cannot be undone.",
    requiredUsername: "Please enter a username.", requiredPassword: "Please enter a password.", submitting: "One moment…",
    loginSuccess: "You’re in. Good to see you!", signupSuccess: "Account created. You can log in now.",
    genericError: "Something didn’t work. Please try again.", networkError: "Couldn’t reach the server. Make sure Flask is running and try again.",
    timeoutError: "The server took too long to respond. Try again in a moment.", invalidCredentials: "That username or password is incorrect.",
    usernameExists: "That username already exists.", missingCredentials: "Please enter a username and password.",
    loadingFeed: "Loading your circle", feedEmptyTitle: "It’s quiet here", feedEmptyCopy: "Posts from your connected friends will appear here.",
    feedErrorTitle: "We couldn’t load your feed", feedErrorCopy: "The feed isn’t available right now. You can try again.", retry: "Try again",
    postCreated: "Your post was published.", postDeleted: "The post was deleted.", postCreateError: "We couldn’t publish your post.",
    comments: "Comments", noComments: "No comments yet. You can start the conversation.", commentPlaceholder: "Write a comment…",
    reply: "Reply", replyingTo: "Replying to {name}", cancelReply: "Cancel reply", commentAdded: "Your comment was added.",
    commentError: "We couldn’t add your comment.", deleteError: "We couldn’t delete the post.", unknownUser: "Unknown user",
    userNumber: "User #{id}", sendRequest: "Send request", sending: "Sending…", requestSent: "Request sent",
    requestSentToast: "Friend request sent.", requestError: "We couldn’t send the friend request.",
    peopleEmptyTitle: "No other people yet", peopleEmptyCopy: "New members will appear here when they join.",
    noResultsTitle: "No match found", noResultsCopy: "Try another name or clear your search.",
    peopleErrorTitle: "We couldn’t load people", peopleErrorCopy: "The user directory isn’t available right now.",
    requestsEmptyTitle: "No pending requests", requestsEmptyCopy: "New friend requests will appear here.",
    requestsErrorTitle: "We couldn’t load requests", requestsErrorCopy: "Requests aren’t available right now.",
    pendingRequest: "Sent you a friend request", pendingOnly: "Waiting for approval", approve: "Approve", reject: "Reject",
    requestApproved: "Friend request approved.", requestRejected: "Friend request rejected.", requestHandleError: "We couldn’t update the request.",
    noPreviewRequests: "No new requests right now.", loggedOut: "You’re logged out.", sessionRestored: "Your session was restored.",
    unauthorized: "Access was denied. Try logging out and back in.", alreadyRequested: "A request already exists or this action isn’t available.",
    postNotFound: "The post could not be found.", invalidPost: "The post ID is invalid.", writeSomething: "Write something before publishing.",
    welcomeBack: "Hello, {name}", loading: "Loading…"
  }
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const t = (key, values = {}) => {
  let value = translations[state.language]?.[key] ?? translations.en[key] ?? key;
  Object.entries(values).forEach(([name, replacement]) => { value = value.replace(`{${name}}`, replacement); });
  return value;
};

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);
}

function icon(name, className = "") {
  return `<svg class="icon ${className}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

function initials(name) {
  const clean = String(name || "?").trim();
  return [...clean][0]?.toUpperCase() || "?";
}

function avatarStyle(name) {
  const palettes = [
    ["#6d65e7", "#4e48b9"], ["#b46a91", "#874b6d"], ["#4e9b7b", "#33745a"],
    ["#d17a55", "#a25437"], ["#498eae", "#326a86"], ["#9470c0", "#694a91"]
  ];
  const hash = [...String(name)].reduce((total, char) => total + char.codePointAt(0), 0);
  const [first, second] = palettes[hash % palettes.length];
  return `background:linear-gradient(145deg,${first},${second})`;
}

function avatarHTML(name, size = "") {
  return `<span class="avatar ${size}" style="${avatarStyle(name)}" aria-hidden="true">${escapeHTML(initials(name))}</span>`;
}

function userName(userID) {
  return state.userMap.get(Number(userID))?.username || t("unknownUser");
}

function setButtonLoading(button, loading) {
  if (!button) return;
  button.classList.toggle("is-loading", loading);
  button.disabled = loading;
  button.setAttribute("aria-busy", String(loading));
}

// ---------- Language and theme ----------

function setLanguage(language, persist = true) {
  state.language = language === "en" ? "en" : "he";
  document.documentElement.lang = state.language;
  document.documentElement.dir = state.language === "he" ? "rtl" : "ltr";
  if (persist) localStorage.setItem(CONFIG.storage.language, state.language);

  $$('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
  $$('[data-i18n-placeholder]').forEach(element => { element.placeholder = t(element.dataset.i18nPlaceholder); });
  $$('[data-i18n-aria]').forEach(element => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
  $$('[data-language-label]').forEach(element => { element.textContent = state.language === "he" ? "English" : "עברית"; });
  $$('[data-set-language]').forEach(button => button.classList.toggle("is-active", button.dataset.setLanguage === state.language));
  document.title = CONFIG.productName;
  updateAuthMode(state.authMode);
  updateThemeLabels();
  updateCurrentUserUI();

  if (state.userID) {
    renderFeedState();
    renderPeople();
    renderRequestsState();
    renderRequestsPreviewState();
  }
}

function initialTheme() {
  if (state.theme === "light" || state.theme === "dark") return state.theme;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(theme, persist = true) {
  state.theme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = state.theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", state.theme === "dark" ? "#101216" : "#f4f5f7");
  if (persist) localStorage.setItem(CONFIG.storage.theme, state.theme);
  updateThemeLabels();
}

function updateThemeLabels() {
  $$('[data-theme-label]').forEach(element => { element.textContent = state.theme === "dark" ? t("lightMode") : t("darkMode"); });
}

function toggleTheme() {
  setTheme(state.theme === "dark" ? "light" : "dark");
}

// ---------- API ----------

class APIError extends Error {
  constructor(message, status = 0, payload = null) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.payload = payload;
  }
}

async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), CONFIG.requestTimeout);
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  try {
    const response = await fetch(path, { ...options, headers, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new APIError(payload?.error || response.statusText, response.status, payload);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new APIError("timeout", 408);
    if (error instanceof APIError) throw error;
    throw new APIError("network", 0);
  } finally {
    window.clearTimeout(timeout);
  }
}

function errorTranslation(error, fallback = "genericError") {
  const raw = String(error?.message || "").toLowerCase();
  if (error?.status === 408 || raw === "timeout") return t("timeoutError");
  if (error?.status === 0 || raw === "network") return t("networkError");
  if (error?.status === 401) return raw.includes("invalid") ? t("invalidCredentials") : t("unauthorized");
  if (raw.includes("username already exists")) return t("usernameExists");
  if (raw.includes("missing username")) return t("missingCredentials");
  if (raw.includes("already following") || raw.includes("invalid request")) return t("alreadyRequested");
  if (raw.includes("request not found")) return t("requestHandleError");
  if (raw.includes("post not found")) return t("postNotFound");
  if (raw.includes("invalid post_id")) return t("invalidPost");
  return t(fallback);
}

// ---------- Toasts and shared states ----------

function showToast(message, type = "info") {
  const region = $("#toast-region");
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.innerHTML = `
    <span class="toast-icon">${icon(type === "success" ? "check" : type === "error" ? "x" : "bell")}</span>
    <p dir="auto">${escapeHTML(message)}</p>
    <button class="icon-button toast-close" type="button" aria-label="${escapeHTML(t("close"))}">${icon("x")}</button>`;
  region.append(toast);
  const dismiss = () => {
    if (!toast.isConnected || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 190);
  };
  $(".toast-close", toast).addEventListener("click", dismiss);
  window.setTimeout(dismiss, CONFIG.toastDuration);
}

function emptyState(titleKey, copyKey, retryAction = "", isError = false) {
  return `<div class="empty-state ${isError ? "error-state" : ""}"><div><div class="empty-visual" aria-hidden="true"></div><h2>${escapeHTML(t(titleKey))}</h2><p>${escapeHTML(t(copyKey))}</p>${retryAction ? `<button class="button button--secondary button--small" type="button" data-retry="${retryAction}">${icon("refresh")}<span>${escapeHTML(t("retry"))}</span></button>` : ""}</div></div>`;
}

function renderSkeleton(container, count = 3) {
  container.innerHTML = Array.from({ length: count }, () => `
    <div class="card skeleton-card" aria-hidden="true"><div class="skeleton-header"><span class="skeleton skeleton-avatar"></span><span class="skeleton-lines"><i class="skeleton skeleton-line"></i><i class="skeleton skeleton-line skeleton-line--short"></i></span></div><div class="skeleton skeleton-body"></div><div class="skeleton skeleton-body"></div></div>`).join("");
}

function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, Number.parseInt(getComputedStyle(textarea).maxHeight) || 220)}px`;
}

// ---------- Authentication ----------

function updateAuthMode(mode) {
  state.authMode = mode === "signup" ? "signup" : "login";
  $$('[data-auth-mode]').forEach(button => {
    const active = button.dataset.authMode === state.authMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  const password = $("#password");
  if (password) password.autocomplete = state.authMode === "signup" ? "new-password" : "current-password";
  const label = $("#auth-submit .button-label");
  if (label) label.textContent = t(state.authMode === "login" ? "loginButton" : "signupButton");
  clearAuthErrors();
}

function clearAuthErrors() {
  $("#username-error").textContent = "";
  $("#password-error").textContent = "";
  $("#username").removeAttribute("aria-invalid");
  $("#password").removeAttribute("aria-invalid");
  const message = $("#auth-message");
  message.textContent = "";
  message.className = "form-message";
}

function validateAuth(username, password) {
  clearAuthErrors();
  let valid = true;
  if (!username.trim()) {
    $("#username-error").textContent = t("requiredUsername");
    $("#username").setAttribute("aria-invalid", "true");
    valid = false;
  }
  if (!password) {
    $("#password-error").textContent = t("requiredPassword");
    $("#password").setAttribute("aria-invalid", "true");
    valid = false;
  }
  return valid;
}

async function submitAuth(event) {
  event.preventDefault();
  const username = $("#username").value.trim();
  const password = $("#password").value;
  if (!validateAuth(username, password)) return;

  const button = $("#auth-submit");
  const message = $("#auth-message");
  setButtonLoading(button, true);
  message.textContent = t("submitting");
  message.className = "form-message";
  try {
    const result = await apiFetch(state.authMode === "login" ? "/login" : "/signup", {
      method: "POST", body: JSON.stringify({ username, password })
    });
    $("#password").value = "";
    if (state.authMode === "signup") {
      message.textContent = t("signupSuccess");
      message.classList.add("is-success");
      updateAuthMode("login");
      $("#username").value = username;
      $("#password").focus();
      showToast(t("signupSuccess"), "success");
      return;
    }
    state.userID = Number(result.userID);
    state.username = String(result.username || username);
    localStorage.setItem(CONFIG.storage.userID, String(state.userID));
    localStorage.setItem(CONFIG.storage.username, state.username);
    showApplication();
    showToast(t("loginSuccess"), "success");
    await loadInitialData();
  } catch (error) {
    message.textContent = errorTranslation(error);
    message.className = "form-message";
  } finally {
    setButtonLoading(button, false);
  }
}

function logout() {
  localStorage.removeItem(CONFIG.storage.userID);
  localStorage.removeItem(CONFIG.storage.username);
  state.userID = null;
  state.username = "";
  state.users = [];
  state.userMap.clear();
  state.posts = [];
  state.requests = [];
  state.feedStatus = "idle";
  state.usersStatus = "idle";
  state.requestsStatus = "idle";
  state.sentRequests.clear();
  $("#main-app").hidden = true;
  $("#auth-screen").hidden = false;
  $("#auth-form").reset();
  updateAuthMode("login");
  $("#username").focus();
  showToast(t("loggedOut"), "info");
}

function showApplication() {
  $("#auth-screen").hidden = true;
  $("#main-app").hidden = false;
  updateCurrentUserUI();
  switchView("feed", false);
}

function updateCurrentUserUI() {
  $$('[data-product-name]').forEach(element => { element.textContent = CONFIG.productName; });
  $$('[data-current-username]').forEach(element => { element.textContent = state.username; });
  $$('[data-current-id]').forEach(element => { element.textContent = state.userID ? t("userNumber", { id: state.userID }) : ""; });
  $$('[data-current-avatar]').forEach(element => {
    element.textContent = initials(state.username);
    element.style.cssText = avatarStyle(state.username);
    element.setAttribute("aria-label", state.username || t("profile"));
  });
}

// ---------- Navigation and data ----------

function switchView(view, focus = true) {
  if (!$( `[data-view="${view}"]` )) return;
  state.activeView = view;
  $$('[data-view]').forEach(section => {
    const active = section.dataset.view === view;
    section.hidden = !active;
    section.classList.toggle("is-active", active);
  });
  $$('[data-view-target]').forEach(button => button.classList.toggle("is-active", button.dataset.viewTarget === view));
  if (view === "people") renderPeople();
  if (view === "requests") loadFriendRequests();
  if (focus) {
    $("#content")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

async function loadInitialData() {
  renderSkeleton($("#feed-list"), 3);
  $("#requests-preview").innerHTML = `<p class="context-empty">${escapeHTML(t("loading"))}</p>`;
  try {
    await loadUsers();
    renderPeople();
  } catch (error) {
    $("#people-list").innerHTML = emptyState("peopleErrorTitle", "peopleErrorCopy", "people", true);
  }
  await Promise.allSettled([loadFeed(), loadFriendRequests()]);
}

async function loadUsers(force = false) {
  if (state.users.length && !force) return state.users;
  state.usersStatus = "loading";
  try {
    const users = await apiFetch("/users");
    state.users = Array.isArray(users) ? users : [];
    state.userMap = new Map(state.users.map(user => [Number(user.userID), user]));
    state.usersStatus = "success";
    return state.users;
  } catch (error) {
    state.usersStatus = "error";
    throw error;
  }
}

async function loadFeed() {
  const container = $("#feed-list");
  state.feedStatus = "loading";
  renderSkeleton(container, 3);
  try {
    const posts = await apiFetch(`/posts/${encodeURIComponent(state.userID)}`);
    state.posts = Array.isArray(posts) ? posts : [];
    state.feedStatus = "success";
    renderFeed(state.posts);
  } catch (error) {
    state.feedStatus = "error";
    container.innerHTML = emptyState("feedErrorTitle", "feedErrorCopy", "feed", true);
  }
}

function renderFeedState() {
  const container = $("#feed-list");
  if (!container) return;
  if (state.feedStatus === "loading") renderSkeleton(container, 3);
  else if (state.feedStatus === "error") container.innerHTML = emptyState("feedErrorTitle", "feedErrorCopy", "feed", true);
  else renderFeed(state.posts);
}

function renderFeed(posts) {
  const container = $("#feed-list");
  if (!posts.length) {
    container.innerHTML = `<div class="card">${emptyState("feedEmptyTitle", "feedEmptyCopy")}</div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  posts.forEach(post => fragment.append(renderPost(post)));
  container.replaceChildren(fragment);
}

function renderPost(post) {
  const article = document.createElement("article");
  const postID = String(post._id || "");
  const author = userName(post.userID);
  const comments = Array.isArray(post.comments) ? post.comments : [];
  const owned = Number(post.userID) === state.userID;
  article.className = "post-card card";
  article.dataset.postId = postID;
  article.innerHTML = `
    <div class="post-main">
      <header class="post-header">
        ${avatarHTML(author)}
        <div class="post-author"><strong dir="auto">${escapeHTML(author)}</strong><span>${escapeHTML(t("userNumber", { id: post.userID }))}</span></div>
        ${owned ? `<button class="icon-button post-delete" type="button" data-delete-post="${escapeHTML(postID)}" aria-label="${escapeHTML(t("deletePost"))}">${icon("trash")}</button>` : ""}
      </header>
      <p class="post-content" dir="auto">${escapeHTML(post.content)}</p>
      <div class="post-meta">${icon("message")}<span>${comments.length} ${escapeHTML(t("comments"))}</span></div>
    </div>
    <section class="comments-section" aria-label="${escapeHTML(t("comments"))}">
      <div class="comments-list">${renderComments(comments)}</div>
      <form class="comment-composer" data-comment-form="${escapeHTML(postID)}">
        ${avatarHTML(state.username, "avatar--sm")}
        <div class="comment-input-wrap">
          <div class="replying-to"><span data-reply-label></span><button class="cancel-reply" type="button" data-cancel-reply="${escapeHTML(postID)}" aria-label="${escapeHTML(t("cancelReply"))}">${icon("x")}</button></div>
          <label class="sr-only" for="comment-${escapeHTML(postID)}">${escapeHTML(t("commentPlaceholder"))}</label>
          <textarea class="comment-input" id="comment-${escapeHTML(postID)}" name="comment" rows="1" maxlength="1000" data-post-id="${escapeHTML(postID)}" placeholder="${escapeHTML(t("commentPlaceholder"))}"></textarea>
        </div>
        <button class="comment-submit" type="submit" disabled aria-label="${escapeHTML(t("publish"))}">${icon("send")}<span class="spinner"></span></button>
      </form>
    </section>`;
  return article;
}

function buildCommentTree(comments) {
  const nodes = new Map();
  comments.forEach(comment => nodes.set(String(comment._id), { ...comment, children: [] }));
  const roots = [];
  nodes.forEach(node => {
    const parentID = node.replyTo ? String(node.replyTo) : null;
    const parent = parentID ? nodes.get(parentID) : null;
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  });
  return roots;
}

function renderComments(comments) {
  if (!comments.length) return `<p class="comments-empty">${escapeHTML(t("noComments"))}</p>`;
  const renderNode = (comment, depth = 0, seen = new Set()) => {
    const commentID = String(comment._id || "");
    if (seen.has(commentID)) return "";
    const nextSeen = new Set(seen).add(commentID);
    const author = userName(comment.userID);
    const safeDepth = Math.min(depth, 3);
    return `<div class="comment" data-depth="${safeDepth}" style="--depth:${safeDepth}">
      ${avatarHTML(author, "avatar--sm")}
      <div class="comment-bubble"><strong class="comment-author" dir="auto">${escapeHTML(author)}</strong><p class="comment-content" dir="auto">${escapeHTML(comment.content)}</p><button class="reply-action" type="button" data-reply-post="${escapeHTML(String(comment.postID || ""))}" data-reply-comment="${escapeHTML(commentID)}" data-reply-name="${escapeHTML(author)}">${escapeHTML(t("reply"))}</button></div>
    </div>${(comment.children || []).map(child => renderNode(child, depth + 1, nextSeen)).join("")}`;
  };
  return buildCommentTree(comments).map(comment => renderNode(comment)).join("");
}

async function createPost() {
  const textarea = $("#post-content");
  const content = textarea.value.trim();
  if (!content) {
    showToast(t("writeSomething"), "info");
    return;
  }
  const button = $("#create-post");
  setButtonLoading(button, true);
  try {
    await apiFetch("/my/post/add", {
      method: "POST", headers: { "User-Id": String(state.userID) }, body: JSON.stringify({ content })
    });
    textarea.value = "";
    autoGrow(textarea);
    updatePostCounter();
    showToast(t("postCreated"), "success");
    await loadFeed();
  } catch (error) {
    showToast(errorTranslation(error, "postCreateError"), "error");
  } finally {
    setButtonLoading(button, false);
    updatePostCounter();
  }
}

function startReply(postID, commentID, name) {
  state.replyTargets.set(postID, { commentID, name });
  const form = $(`[data-comment-form="${CSS.escape(postID)}"]`);
  if (!form) return;
  const banner = $(".replying-to", form);
  $("[data-reply-label]", banner).textContent = t("replyingTo", { name });
  banner.classList.add("is-active");
  $(".comment-input", form).focus();
}

function cancelReply(postID) {
  state.replyTargets.delete(postID);
  const form = $(`[data-comment-form="${CSS.escape(postID)}"]`);
  $(".replying-to", form)?.classList.remove("is-active");
}

async function submitComment(form) {
  const postID = form.dataset.commentForm;
  const textarea = $(".comment-input", form);
  const content = textarea.value.trim();
  if (!content) return;
  const button = $(".comment-submit", form);
  const replyTarget = state.replyTargets.get(postID);
  const body = { post_id: postID, content };
  if (replyTarget) body.replyTo = replyTarget.commentID;
  setButtonLoading(button, true);
  try {
    await apiFetch("/my/post/comment", {
      method: "POST", headers: { "User-Id": String(state.userID) }, body: JSON.stringify(body)
    });
    textarea.value = "";
    cancelReply(postID);
    showToast(t("commentAdded"), "success");
    await loadFeed();
  } catch (error) {
    showToast(errorTranslation(error, "commentError"), "error");
    setButtonLoading(button, false);
    button.disabled = !textarea.value.trim();
  }
}

// ---------- Delete modal ----------

function openDeleteModal(postID, source) {
  state.deletePostID = postID;
  state.lastModalFocus = source || document.activeElement;
  const backdrop = $("#modal-backdrop");
  backdrop.hidden = false;
  document.body.style.overflow = "hidden";
  $("#modal-cancel").focus();
}

function closeModal() {
  const backdrop = $("#modal-backdrop");
  if (backdrop.hidden) return;
  backdrop.hidden = true;
  document.body.style.overflow = "";
  state.deletePostID = null;
  state.lastModalFocus?.focus?.();
}

async function confirmDelete() {
  if (!state.deletePostID) return;
  const postID = state.deletePostID;
  const button = $("#modal-confirm");
  setButtonLoading(button, true);
  try {
    await apiFetch("/my/post/delete", {
      method: "POST", headers: { "User-Id": String(state.userID) }, body: JSON.stringify({ post_id: postID })
    });
    const card = $(`[data-post-id="${CSS.escape(postID)}"]`);
    card?.classList.add("is-removing");
    closeModal();
    showToast(t("postDeleted"), "success");
    window.setTimeout(() => loadFeed(), 210);
  } catch (error) {
    showToast(errorTranslation(error, "deleteError"), "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function trapModalFocus(event) {
  const modal = $("#modal-backdrop");
  if (modal.hidden || event.key !== "Tab") return;
  const focusable = $$('button:not(:disabled)', modal);
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

// ---------- People and friend requests ----------

function renderPeople() {
  const container = $("#people-list");
  if (!container) return;
  if (state.usersStatus === "error") {
    container.innerHTML = emptyState("peopleErrorTitle", "peopleErrorCopy", "people", true);
    return;
  }
  if (!state.users.length) {
    container.innerHTML = emptyState("peopleEmptyTitle", "peopleEmptyCopy");
    return;
  }
  const query = $("#people-search")?.value.trim().toLocaleLowerCase(state.language === "he" ? "he" : "en") || "";
  const people = state.users.filter(user => Number(user.userID) !== state.userID && String(user.username).toLocaleLowerCase().includes(query));
  if (!people.length) {
    container.innerHTML = emptyState(query ? "noResultsTitle" : "peopleEmptyTitle", query ? "noResultsCopy" : "peopleEmptyCopy");
    return;
  }
  container.innerHTML = people.map(user => {
    const id = Number(user.userID);
    const sent = state.sentRequests.has(id);
    return `<div class="directory-row" data-person-id="${id}">${avatarHTML(user.username)}<div class="directory-copy"><strong dir="auto">${escapeHTML(user.username)}</strong><span>${escapeHTML(t("userNumber", { id }))}</span></div>${sent ? `<span class="sent-label">${icon("check")} ${escapeHTML(t("requestSent"))}</span>` : `<button class="button button--secondary button--small" type="button" data-send-request="${id}">${icon("plus-user")}<span>${escapeHTML(t("sendRequest"))}</span><span class="spinner"></span></button>`}</div>`;
  }).join("");
}

async function sendFriendRequest(targetID, button) {
  setButtonLoading(button, true);
  try {
    await apiFetch(`/friend-request/${encodeURIComponent(state.userID)}/${encodeURIComponent(targetID)}`, { method: "POST" });
    state.sentRequests.add(Number(targetID));
    renderPeople();
    showToast(t("requestSentToast"), "success");
  } catch (error) {
    setButtonLoading(button, false);
    showToast(errorTranslation(error, "requestError"), "error");
  }
}

async function loadFriendRequests() {
  const container = $("#requests-list");
  state.requestsStatus = "loading";
  if (state.activeView === "requests") renderSkeleton(container, 2);
  try {
    const requests = await apiFetch("/my/requests", { headers: { "User-Id": String(state.userID) } });
    state.requests = Array.isArray(requests) ? requests : [];
    state.requestsStatus = "success";
    renderRequests();
    renderRequestsPreview();
    updateRequestBadges();
  } catch (error) {
    state.requests = [];
    state.requestsStatus = "error";
    if (container) container.innerHTML = emptyState("requestsErrorTitle", "requestsErrorCopy", "requests", true);
    $("#requests-preview").innerHTML = `<p class="context-empty">${escapeHTML(t("requestsErrorCopy"))}</p>`;
    updateRequestBadges();
  }
}

function renderRequestsState() {
  const container = $("#requests-list");
  if (!container) return;
  if (state.requestsStatus === "loading") renderSkeleton(container, 2);
  else if (state.requestsStatus === "error") container.innerHTML = emptyState("requestsErrorTitle", "requestsErrorCopy", "requests", true);
  else renderRequests();
}

function renderRequestsPreviewState() {
  const container = $("#requests-preview");
  if (!container) return;
  if (state.requestsStatus === "loading") container.innerHTML = `<p class="context-empty">${escapeHTML(t("loading"))}</p>`;
  else if (state.requestsStatus === "error") container.innerHTML = `<p class="context-empty">${escapeHTML(t("requestsErrorCopy"))}</p>`;
  else renderRequestsPreview();
}

function renderRequests() {
  const container = $("#requests-list");
  if (!container) return;
  if (!state.requests.length) {
    container.innerHTML = emptyState("requestsEmptyTitle", "requestsEmptyCopy");
    return;
  }
  container.innerHTML = state.requests.map(request => {
    const id = Number(request.follower_id);
    const name = userName(id);
    return `<div class="directory-row" data-request-id="${id}">${avatarHTML(name)}<div class="directory-copy"><strong dir="auto">${escapeHTML(name)}</strong><span>${escapeHTML(t("pendingRequest"))}</span></div><div class="request-actions"><button class="button button--secondary button--small" type="button" data-handle-request="${id}" data-request-action="reject"><span>${escapeHTML(t("reject"))}</span><span class="spinner"></span></button><button class="button button--primary button--small" type="button" data-handle-request="${id}" data-request-action="approve">${icon("check")}<span>${escapeHTML(t("approve"))}</span><span class="spinner"></span></button></div></div>`;
  }).join("");
}

async function handleFriendRequest(followerID, action, button) {
  const row = button.closest("[data-request-id]");
  const buttons = $$('[data-handle-request]', row);
  buttons.forEach(item => { item.disabled = true; });
  setButtonLoading(button, true);
  try {
    await apiFetch(`/my/requests/${encodeURIComponent(followerID)}/${action}`, {
      method: "PUT", headers: { "User-Id": String(state.userID) }
    });
    state.requests = state.requests.filter(request => Number(request.follower_id) !== Number(followerID));
    renderRequests();
    renderRequestsPreview();
    updateRequestBadges();
    showToast(t(action === "approve" ? "requestApproved" : "requestRejected"), "success");
    if (action === "approve") await loadFeed();
  } catch (error) {
    buttons.forEach(item => { item.disabled = false; });
    setButtonLoading(button, false);
    showToast(errorTranslation(error, "requestHandleError"), "error");
  }
}

function renderRequestsPreview() {
  const container = $("#requests-preview");
  if (!container) return;
  if (!state.requests.length) {
    container.innerHTML = `<p class="context-empty">${escapeHTML(t("noPreviewRequests"))}</p>`;
    return;
  }
  container.innerHTML = state.requests.slice(0, 3).map(request => {
    const id = Number(request.follower_id);
    const name = userName(id);
    return `<div class="preview-row">${avatarHTML(name, "avatar--xs")}<div class="preview-copy"><strong dir="auto">${escapeHTML(name)}</strong><span>${escapeHTML(t("pendingOnly"))}</span></div></div>`;
  }).join("");
}

function updateRequestBadges() {
  $$('[data-request-badge]').forEach(badge => {
    badge.hidden = state.requests.length === 0;
    badge.textContent = state.requests.length > 99 ? "99+" : String(state.requests.length);
  });
}

// ---------- Events ----------

function updatePostCounter() {
  const textarea = $("#post-content");
  const length = textarea.value.length;
  $("#post-counter").textContent = `${length} / 2000`;
  $("#create-post").disabled = !textarea.value.trim();
}

function bindEvents() {
  $("#auth-form").addEventListener("submit", submitAuth);
  $$('[data-auth-mode]').forEach(button => button.addEventListener("click", () => updateAuthMode(button.dataset.authMode)));
  $("#password-toggle").addEventListener("click", event => {
    const input = $("#password");
    const visible = input.type === "text";
    input.type = visible ? "password" : "text";
    event.currentTarget.classList.toggle("is-visible", !visible);
    event.currentTarget.setAttribute("aria-label", t(visible ? "showPassword" : "hidePassword"));
  });
  [$("#username"), $("#password")].forEach(input => input.addEventListener("input", () => {
    input.removeAttribute("aria-invalid");
    $(`#${input.id}-error`).textContent = "";
  }));
  $$('[data-language-toggle]').forEach(button => button.addEventListener("click", () => setLanguage(state.language === "he" ? "en" : "he")));
  $$('[data-set-language]').forEach(button => button.addEventListener("click", () => setLanguage(button.dataset.setLanguage)));
  $$('[data-theme-toggle]').forEach(button => button.addEventListener("click", toggleTheme));
  $$('[data-view-target]').forEach(button => button.addEventListener("click", event => { event.preventDefault(); switchView(button.dataset.viewTarget); }));
  $$('[data-compose-focus]').forEach(button => button.addEventListener("click", () => { switchView("feed"); window.setTimeout(() => $("#post-content").focus(), 80); }));
  [$("#sidebar-logout"), $("#settings-logout")].forEach(button => button.addEventListener("click", logout));

  $("#post-content").addEventListener("input", event => { autoGrow(event.target); updatePostCounter(); });
  $("#post-content").addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && event.currentTarget.value.trim()) createPost();
  });
  $("#create-post").addEventListener("click", createPost);
  $("#refresh-feed").addEventListener("click", loadFeed);
  $("#refresh-requests").addEventListener("click", loadFriendRequests);
  $("#people-search").addEventListener("input", renderPeople);

  $("#main-app").addEventListener("input", event => {
    if (!event.target.matches(".comment-input")) return;
    autoGrow(event.target);
    const button = $(".comment-submit", event.target.closest("form"));
    button.disabled = !event.target.value.trim();
  });
  $("#main-app").addEventListener("submit", event => {
    const form = event.target.closest("[data-comment-form]");
    if (!form) return;
    event.preventDefault();
    submitComment(form);
  });
  $("#main-app").addEventListener("click", event => {
    const deleteButton = event.target.closest("[data-delete-post]");
    const replyButton = event.target.closest("[data-reply-comment]");
    const cancelButton = event.target.closest("[data-cancel-reply]");
    const requestButton = event.target.closest("[data-send-request]");
    const handleRequestButton = event.target.closest("[data-handle-request]");
    const retryButton = event.target.closest("[data-retry]");
    if (deleteButton) openDeleteModal(deleteButton.dataset.deletePost, deleteButton);
    else if (replyButton) startReply(replyButton.dataset.replyPost, replyButton.dataset.replyComment, replyButton.dataset.replyName);
    else if (cancelButton) cancelReply(cancelButton.dataset.cancelReply);
    else if (requestButton) sendFriendRequest(Number(requestButton.dataset.sendRequest), requestButton);
    else if (handleRequestButton) handleFriendRequest(Number(handleRequestButton.dataset.handleRequest), handleRequestButton.dataset.requestAction, handleRequestButton);
    else if (retryButton?.dataset.retry === "feed") loadFeed();
    else if (retryButton?.dataset.retry === "requests") loadFriendRequests();
    else if (retryButton?.dataset.retry === "people") loadUsers(true).then(renderPeople).catch(() => { $("#people-list").innerHTML = emptyState("peopleErrorTitle", "peopleErrorCopy", "people", true); });
  });

  $("#modal-close").addEventListener("click", closeModal);
  $("#modal-cancel").addEventListener("click", closeModal);
  $("#modal-confirm").addEventListener("click", confirmDelete);
  $("#modal-backdrop").addEventListener("click", event => { if (event.target === event.currentTarget) closeModal(); });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !$("#modal-backdrop").hidden) closeModal();
    trapModalFocus(event);
  });
}

// ---------- Start ----------

async function init() {
  state.theme = initialTheme();
  setTheme(state.theme, false);
  setLanguage(state.language, false);
  bindEvents();
  updatePostCounter();
  if (state.userID && state.username) {
    showApplication();
    await loadInitialData();
  } else {
    $("#auth-screen").hidden = false;
    $("#main-app").hidden = true;
  }
}

document.addEventListener("DOMContentLoaded", init);
