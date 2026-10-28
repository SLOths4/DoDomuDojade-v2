import { api } from "/shared/api.js";
import { formMixin, fromLocalInput, registerUi, toLocalInput } from "/shared/ui.js";

const VIEWS = ["announcements", "countdowns", "modules", "users", "profile"];
const ADMIN_VIEWS = ["modules", "users"];

const session = () => window.Alpine.store("session");
const ui = () => window.Alpine.store("ui");
const t = (key, params) => session().t(key, params);

function todayIso() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

document.addEventListener("alpine:init", () => {
  const Alpine = window.Alpine;
  registerUi(Alpine);

  Alpine.data("panelApp", () => ({
    view: "announcements",
    loading: true,
    menuOpen: false,

    async init() {
      await session().init();
      try {
        const user = await api("/auth/me");
        await this.signedIn(user);
      } catch {
        session().user = null;
      }
      this.route();
      window.addEventListener("hashchange", () => this.route());
      window.addEventListener("ddd:unauthenticated", () => {
        session().user = null;
      });
      this.loading = false;
    },

    async signedIn(user) {
      if (user.locale !== session().locale) await session().useLocale(user.locale);
      session().user = user;
      this.route();
    },

    t(key, params) {
      return t(key, params);
    },

    get isAdmin() {
      return session().user?.role === "admin";
    },

    get views() {
      return VIEWS.filter((view) => this.isAdmin || !ADMIN_VIEWS.includes(view));
    },

    route() {
      const wanted = window.location.hash.slice(1);
      this.view = this.views.includes(wanted) ? wanted : "announcements";
      this.menuOpen = false;
    },

    async logout() {
      await api("/auth/logout", { method: "POST" }).catch(() => null);
      session().user = null;
      window.location.hash = "";
    },
  }));

  Alpine.data("loginForm", () => ({
    ...formMixin(),
    username: "",
    password: "",

    async login() {
      const user = await this.submit(() =>
        api("/auth/login", { method: "POST", body: { username: this.username, password: this.password } }),
      );
      if (user) {
        this.password = "";
        this.$dispatch("signed-in", user);
      }
    },
  }));

  Alpine.data("passwordForm", () => ({
    ...formMixin(),
    currentPassword: "",
    newPassword: "",
    repeatPassword: "",

    async change() {
      if (this.newPassword !== this.repeatPassword) {
        this.errors = { repeatPassword: t("password.mismatch") };
        return;
      }
      const limits = { newPassword: { min: session().config.password.minLength } };
      const done = await this.submit(
        () =>
          api("/auth/password", {
            method: "POST",
            body: { currentPassword: this.currentPassword, newPassword: this.newPassword },
          }).then(() => true),
        { limits },
      );
      if (done) {
        this.currentPassword = this.newPassword = this.repeatPassword = "";
        session().user = await api("/auth/me");
        ui().toast(t("password.changed"));
      }
    },
  }));

  Alpine.data("announcementsView", () => ({
    items: [],
    loaded: false,
    filter: "all",
    editor: null,

    async init() {
      await this.load();
    },

    async load() {
      try {
        this.items = await api("/announcements");
      } catch (error) {
        ui().error(error);
      }
      this.loaded = true;
    },

    get pending() {
      return this.items.filter((a) => a.status === "pending");
    },

    get decided() {
      const decided = this.items.filter((a) => a.status !== "pending");
      return this.filter === "visible" ? decided.filter((a) => this.isVisible(a)) : decided;
    },

    isVisible(a) {
      return a.status === "approved" && a.validUntil >= todayIso();
    },

    isExpired(a) {
      return a.validUntil < todayIso();
    },

    get limits() {
      const c = session().config.announcement;
      return {
        title: { min: c.titleMinLength, max: c.titleMaxLength },
        text: { min: c.textMinLength, max: c.textMaxLength },
      };
    },

    openNew() {
      this.editor = { id: null, title: "", text: "", validUntil: "" };
    },

    openEdit(a) {
      this.editor = { id: a.id, title: a.title, text: a.text, validUntil: a.validUntil };
    },

    async save(form) {
      const { id, title, text, validUntil } = this.editor;
      const body = { title, text, validUntil: validUntil || null };
      const saved = await form.submit(
        () =>
          id
            ? api(`/announcements/${id}`, { method: "PATCH", body })
            : api("/announcements", { method: "POST", body }),
        { limits: this.limits },
      );
      if (saved) {
        this.editor = null;
        ui().toast(t("common.saved"));
        await this.load();
      }
    },

    async decide(a, action) {
      try {
        await api(`/announcements/${a.id}/${action}`, { method: "POST" });
        ui().toast(t(action === "approve" ? "announcements.approved" : "announcements.rejected"));
        await this.load();
      } catch (error) {
        ui().error(error);
      }
    },

    async remove(a) {
      if (!(await ui().confirm(t("announcements.confirm_delete", { title: a.title }), t("common.delete")))) return;
      try {
        await api(`/announcements/${a.id}`, { method: "DELETE" });
        ui().toast(t("common.deleted"));
        await this.load();
      } catch (error) {
        ui().error(error);
      }
    },
  }));

  Alpine.data("countdownsView", () => ({
    items: [],
    loaded: false,
    editor: null,

    async init() {
      await this.load();
    },

    async load() {
      try {
        this.items = await api("/countdowns");
      } catch (error) {
        ui().error(error);
      }
      this.loaded = true;
    },

    get shownId() {
      const now = Date.now();
      return this.items.find((c) => new Date(c.countTo) > now)?.id;
    },

    isPast(c) {
      return new Date(c.countTo) <= Date.now();
    },

    get limits() {
      const c = session().config.countdown;
      return { title: { min: c.titleMinLength, max: c.titleMaxLength } };
    },

    openNew() {
      this.editor = { id: null, title: "", countTo: "" };
    },

    openEdit(c) {
      this.editor = { id: c.id, title: c.title, countTo: toLocalInput(c.countTo) };
    },

    async save(form) {
      const { id, title, countTo } = this.editor;
      const body = { title, countTo: fromLocalInput(countTo) };
      const saved = await form.submit(
        () =>
          id ? api(`/countdowns/${id}`, { method: "PATCH", body }) : api("/countdowns", { method: "POST", body }),
        { limits: this.limits },
      );
      if (saved) {
        this.editor = null;
        ui().toast(t("common.saved"));
        await this.load();
      }
    },

    async remove(c) {
      if (!(await ui().confirm(t("countdowns.confirm_delete", { title: c.title }), t("common.delete")))) return;
      try {
        await api(`/countdowns/${c.id}`, { method: "DELETE" });
        ui().toast(t("common.deleted"));
        await this.load();
      } catch (error) {
        ui().error(error);
      }
    },
  }));

  Alpine.data("modulesView", () => ({
    items: [],
    loaded: false,

    async init() {
      try {
        this.items = (await api("/modules")).map((m) => ({
          ...m,
          startTime: m.startTime.slice(0, 5),
          endTime: m.endTime.slice(0, 5),
        }));
      } catch (error) {
        ui().error(error);
      }
      this.loaded = true;
    },

    async save(module, form) {
      const body = { isActive: module.isActive, startTime: module.startTime, endTime: module.endTime };
      const saved = await form.submit(() => api(`/modules/${module.id}`, { method: "PATCH", body }));
      if (saved) ui().toast(t("common.saved"));
    },
  }));

  Alpine.data("usersView", () => ({
    items: [],
    loaded: false,
    editor: null,
    reset: null,

    async init() {
      await this.load();
    },

    async load() {
      try {
        this.items = await api("/users");
      } catch (error) {
        ui().error(error);
      }
      this.loaded = true;
    },

    get limits() {
      const c = session().config;
      return { username: { max: c.username.maxLength }, password: { min: c.password.minLength } };
    },

    openNew() {
      this.editor = { id: null, username: "", password: "", role: "moderator", isActive: true };
    },

    openEdit(user) {
      this.editor = { id: user.id, username: user.username, role: user.role, isActive: user.isActive };
    },

    async save(form) {
      const { id, username, password, role, isActive } = this.editor;
      const saved = await form.submit(
        () =>
          id
            ? api(`/users/${id}`, { method: "PATCH", body: { username, role, isActive } })
            : api("/users", { method: "POST", body: { username, password, role } }),
        { limits: this.limits },
      );
      if (saved) {
        this.editor = null;
        ui().toast(t("common.saved"));
        await this.load();
      }
    },

    async resetPassword(form) {
      const done = await form.submit(
        () =>
          api(`/users/${this.reset.id}/password`, {
            method: "POST",
            body: { newPassword: this.reset.newPassword },
          }).then(() => true),
        { limits: { newPassword: { min: session().config.password.minLength } } },
      );
      if (done) {
        this.reset = null;
        ui().toast(t("users.password_reset"));
        await this.load();
      }
    },

    async remove(user) {
      if (!(await ui().confirm(t("users.confirm_delete", { username: user.username }), t("common.delete")))) return;
      try {
        await api(`/users/${user.id}`, { method: "DELETE" });
        ui().toast(t("common.deleted"));
        await this.load();
      } catch (error) {
        ui().error(error);
      }
    },
  }));
});
