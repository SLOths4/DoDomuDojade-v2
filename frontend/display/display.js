const ROTATOR_MODULES = ["countdown", "quote", "word", "calendar"];
// Each slide stays up long enough to read it from across the room:
// a base time plus time per character, clamped to a sensible range.
const SLIDE_BASE_SECONDS = 4;
const SLIDE_CHARS_PER_SECOND = 12;
const SLIDE_MIN_SECONDS = 10;
const SLIDE_MAX_SECONDS = 45;
const ANNOUNCEMENT_SECONDS = 8;
const RECONNECT_DELAY_MS = 5_000;
const FALLBACK_POLL_AFTER_MS = 30_000;
const FALLBACK_POLL_EVERY_MS = 60_000;
// Nobody can press refresh on the TV: after a long outage reload the whole page.
const RELOAD_AFTER_MS = 10 * 60_000;

const LINE_COLOURS = {
  1: "bg-pink-700 text-white",
  2: "bg-2",
  3: "bg-green-500 text-white",
  5: "bg-purple-700 text-white",
  6: "bg-6 text-white",
  7: "bg-teal-500 text-white",
  8: "bg-violet-500 text-white",
  9: "bg-9 text-white",
  10: "bg-slate-500 text-white",
  11: "bg-purple-400 text-white",
  12: "bg-12",
  13: "bg-amber-500",
  14: "bg-green-400",
  15: "bg-blue-400 text-white",
  16: "bg-red-400 text-white",
  17: "bg-red-400 text-white",
  18: "bg-18",
  19: "bg-19 text-white",
};

function plural(n, one, few, many) {
  if (n === 1) return `${n} ${one}`;
  const lastDigit = n % 10;
  const lastTwo = n % 100;
  if (lastDigit >= 2 && lastDigit <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return `${n} ${few}`;
  return `${n} ${many}`;
}

function timeOfDay(iso) {
  return new Date(iso).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
}

function slideText(slide) {
  const d = slide.data ?? {};
  switch (slide.type) {
    case "quote":
      return `${d.text ?? ""} ${d.author ?? ""}`;
    case "word":
      return `${d.word ?? ""} ${d.definition ?? ""}`;
    case "event":
      return `${d.summary ?? ""} ${d.description ?? ""}`;
    default:
      return "";
  }
}

function slideSeconds(slide) {
  const reading = SLIDE_BASE_SECONDS + slideText(slide).trim().length / SLIDE_CHARS_PER_SECOND;
  return Math.min(SLIDE_MAX_SECONDS, Math.max(SLIDE_MIN_SECONDS, Math.ceil(reading)));
}

document.addEventListener("alpine:init", () => {
  window.Alpine.data("screen", () => ({
    modules: {},
    loaded: false,
    connected: false,
    date: "",
    time: "",
    gridHeight: 0,
    maxRows: 50,
    slideIndex: 0,
    slideElapsed: 0,
    announcementIndex: 0,
    countdownText: "",
    disconnectedSince: null,
    pollTimer: null,

    init() {
      this.tick();
      setInterval(() => this.tick(), 1000);
      setInterval(() => this.advance(), 1000);
      this.layout();
      window.addEventListener("resize", () => this.layout());
      this.connect();
      this.$watch("modules", () => this.$nextTick(() => this.fitDepartures()));
    },

    connect() {
      const source = new EventSource("/api/display/stream");
      source.addEventListener("open", () => {
        this.connected = true;
        this.disconnectedSince = null;
        this.stopPolling();
      });
      source.addEventListener("snapshot", (event) => this.applySnapshot(JSON.parse(event.data)));
      source.addEventListener("module", (event) => {
        const { name, ...envelope } = JSON.parse(event.data);
        this.modules = { ...this.modules, [name]: envelope };
      });
      source.addEventListener("error", () => {
        this.connected = false;
        this.disconnectedSince ??= Date.now();
        setTimeout(() => this.startPollingIfStillDown(), FALLBACK_POLL_AFTER_MS);
        // EventSource retries dropped connections itself, but gives up for good after an
        // error response (e.g. 502 while the API restarts), so reconnect by hand.
        if (source.readyState === EventSource.CLOSED) {
          setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
        }
      });
    },

    applySnapshot(snapshot) {
      this.modules = snapshot;
      this.loaded = true;
    },

    startPollingIfStillDown() {
      if (this.connected || this.pollTimer) return;
      const poll = async () => {
        if (Date.now() - (this.disconnectedSince ?? Date.now()) > RELOAD_AFTER_MS) {
          window.location.reload();
          return;
        }
        try {
          const response = await fetch("/api/display", { headers: { Accept: "application/json" } });
          if (response.ok) this.applySnapshot(await response.json());
        } catch {
          // Still offline; keep showing the last known data.
        }
      };
      poll();
      this.pollTimer = setInterval(poll, FALLBACK_POLL_EVERY_MS);
    },

    stopPolling() {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    },

    tick() {
      const now = new Date();
      this.date = now.toLocaleDateString("pl-PL");
      this.time = now.toLocaleTimeString("pl-PL");
      this.updateCountdown(now);
    },

    advance() {
      const seconds = Math.floor(Date.now() / 1000);
      const slides = this.slides;
      const current = slides[this.slideIndex];
      this.slideElapsed += 1;
      if (!current || this.slideElapsed >= slideSeconds(current)) {
        this.slideIndex = slides.length ? (this.slideIndex + 1) % slides.length : 0;
        this.slideElapsed = 0;
      }
      if (seconds % ANNOUNCEMENT_SECONDS === 0) {
        const count = this.announcements.length;
        this.announcementIndex = count ? (this.announcementIndex + 1) % count : 0;
      }
    },

    layout() {
      const header = this.$refs.header;
      const style = getComputedStyle(header);
      const headerHeight =
        header.getBoundingClientRect().height + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
      this.gridHeight = window.innerHeight - headerHeight - 4;
      this.maxRows = 50;
      this.$nextTick(() => this.fitDepartures());
    },

    fitDepartures() {
      const box = this.$refs.departures;
      if (!box) return;
      const limit = box.getBoundingClientRect().bottom - 8;
      const rows = [...box.querySelectorAll("[data-row]")];
      const fitting = rows.filter((row) => row.getBoundingClientRect().bottom <= limit).length;
      if (rows.length && fitting < rows.length) this.maxRows = fitting;
    },

    get departures() {
      const module = this.modules.departures;
      return module?.status === "active" ? module.data : [];
    },

    get visibleDepartures() {
      return this.departures.slice(0, this.maxRows);
    },

    get announcements() {
      const module = this.modules.announcement;
      return module?.status === "active" ? module.data : [];
    },

    get slides() {
      const slides = [];
      const active = (name) => this.modules[name]?.status === "active";
      if (active("countdown")) slides.push({ key: "countdown", type: "countdown", data: this.modules.countdown.data });
      if (active("quote")) slides.push({ key: "quote", type: "quote", data: this.modules.quote.data });
      if (active("word")) slides.push({ key: "word", type: "word", data: this.modules.word.data });
      if (active("calendar")) {
        this.modules.calendar.data.forEach((event, i) =>
          slides.push({ key: `event-${i}-${event.summary}`, type: "event", data: event }),
        );
      }
      return slides;
    },

    get rotatorNotices() {
      return ROTATOR_MODULES.filter((name) => this.modules[name] && this.modules[name].status !== "active").map(
        (name) => ({ name, ...this.modules[name] }),
      );
    },

    updateCountdown(now) {
      const countdown = this.modules.countdown;
      if (countdown?.status !== "active") {
        this.countdownText = "";
        return;
      }
      const diff = new Date(countdown.data.countTo) - now;
      if (diff <= 0) {
        this.countdownText = `${countdown.data.title}: zakończono!`;
        return;
      }
      const days = Math.floor(diff / 86_400_000);
      const hours = Math.floor((diff % 86_400_000) / 3_600_000);
      const minutes = Math.floor((diff % 3_600_000) / 60_000);
      const seconds = Math.floor((diff % 60_000) / 1000);
      this.countdownText = `Do ${countdown.data.title}: ${[
        plural(days, "dzień", "dni", "dni"),
        plural(hours, "godzina", "godziny", "godzin"),
        plural(minutes, "minuta", "minuty", "minut"),
        plural(seconds, "sekunda", "sekundy", "sekund"),
      ].join(" ")}`;
    },

    formatMinutes(minutes) {
      if (minutes === 0) return "<1 min";
      if (minutes < 60) return `${minutes} min`;
      return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
    },

    lineBadge(departure) {
      const size = "h-11 max-2xl:h-10 max-xl:h-9 max-lg:h-8 max-md:h-6 max-sm:h-5";
      if (departure.vehicle === "tram") {
        const width = "w-11 max-2xl:w-10 max-xl:w-9 max-lg:w-8 max-md:w-6 max-sm:w-5";
        return `${size} ${width} rounded-full ${LINE_COLOURS[departure.line] ?? "bg-primary text-white"}`;
      }
      return `${size} min-w-13 px-1 rounded-md border border-gray-400 max-lg:min-w-10 max-md:min-w-8`;
    },

    eventTime(event) {
      if (event.allDay) return "Cały dzień";
      return event.end ? `${timeOfDay(event.start)}–${timeOfDay(event.end)}` : timeOfDay(event.start);
    },

    temperatureColour(t) {
      if (t === null) return "#6b7280";
      if (t <= -10) return "#1E40AF";
      if (t <= 0) return "#0EA5E9";
      if (t <= 5) return "#FFB3B3";
      if (t <= 15) return "#FCD34D";
      if (t <= 25) return "#F97316";
      return "#DC2626";
    },

    alertClass(status) {
      return { empty: "d-alert-empty", inactive: "d-alert-inactive" }[status] ?? "d-alert-error";
    },

    alertIcon(status) {
      return { empty: "fa-circle-info", inactive: "fa-power-off" }[status] ?? "fa-triangle-exclamation";
    },
  }));
});
