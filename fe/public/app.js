// Passenger web shell (spec passenger-web).
//
// This page never reads, stores or sends the API token itself: the browser's
// header-modifier extension adds Authorization to requests for this origin.

const MESSAGES = {
  checking: "Checking connection…",
  connected: "Connected",
  unauthorized: "Missing or invalid token",
  unavailable: "Service unavailable",
};

function stateFor(status) {
  if (status === 200) return "connected";
  if (status === 401) return "unauthorized";
  return "unavailable";
}

// ---- trip lookup (spec passenger-web) ---------------------------------------------
// The page only renders what the API decided. It never stores the booking code or the
// surname, never puts them in the URL, and never converts time zones: the API sends
// local times with their offset, and the page shows the wall-clock part as is.

const LOOKUP_ERRORS = {
  401: "Missing or invalid token",
  404: "We couldn't find a booking with those details",
  422: "Please check the booking code and last name",
  429: "Too many attempts, please wait a moment",
};
const UNAVAILABLE = "Service unavailable, please try again shortly";

const STATUS_TEXT = {
  ON_SCHEDULE: "On schedule",
  DELAYED: "Delayed",
  CANCELLED: "Cancelled",
  UNVERIFIED: "Being confirmed",
};
const CONNECTION_TEXT = {
  OK: "Connection still possible",
  MISSED: "Connection will be missed",
  UNREACHABLE: "Affected by the cancellation",
  UNKNOWN: "Being confirmed",
};
const TYPE_TEXT = { ADULT: "adult", CHILD: "child", INFANT: "infant" };

function localTime(iso, airport) {
  // "2026-09-15T20:35:00-05:00" -> "20:35 LIM" (no conversion to the browser's zone)
  return iso ? `${iso.slice(11, 16)} ${airport ?? ""}`.trim() : "";
}

function segmentView(s) {
  const estimated = s.estimated_departure
    ? `${localTime(s.estimated_departure, s.origin)} → ${localTime(s.estimated_arrival, s.destination)}`
    : "";
  return {
    key: s.segment_id,
    title: `${s.flight_number} ${s.origin ?? "?"} → ${s.destination ?? "?"}`,
    scheduled: `${localTime(s.scheduled_departure, s.origin)} → ${localTime(s.scheduled_arrival, s.destination)}`,
    estimated,
    hasEstimate: Boolean(estimated),
    gate: s.gate ?? "",
    hasGate: Boolean(s.gate),
    statusText: STATUS_TEXT[s.status] ?? s.status,
    statusClass: s.status.toLowerCase(),
    connection: s.connection ? CONNECTION_TEXT[s.connection.status] : "",
    connectionClass: s.connection ? s.connection.status.toLowerCase() : "",
    hasConnection: Boolean(s.connection),
  };
}

function tripView(body) {
  return {
    headline: body.explanation.headline,
    details: body.explanation.details,
    passengers:
      "Passengers: " +
      body.passengers.map((p) => `${p.first_name} (${TYPE_TEXT[p.type] ?? p.type})`).join(", "),
    segments: body.segments.map(segmentView),
    nextStep: body.next_step,
  };
}

function lookupBody(formData) {
  return {
    booking_id: String(formData.get("booking_id") ?? "").trim(),
    last_name: String(formData.get("last_name") ?? "").trim(),
  };
}

const EMPTY_TRIP = { headline: "", details: [], passengers: "", segments: [], nextStep: "NONE" };

document.addEventListener("alpine:init", () => {
  window.Alpine.data("tripLookup", () => ({
    busy: false,
    error: "",
    trip: EMPTY_TRIP,
    loaded: false,

    get hasError() {
      return this.error !== "";
    },
    get hasTrip() {
      return this.loaded;
    },
    get showOptions() {
      return this.loaded && this.trip.nextStep === "RECOMMENDATION";
    },
    get showAgent() {
      return this.loaded && this.trip.nextStep === "HUMAN_ASSISTANCE";
    },

    // The CSP build calls handlers with the event. Values come from the form itself
    // (x-model does not work in the CSP build) and live only for this request.
    async submit(event) {
      const form = event?.target instanceof HTMLFormElement ? event.target : this.$refs.form;
      const data = new FormData(form);
      this.busy = true;
      this.error = "";
      this.loaded = false;
      try {
        const response = await fetch("/api/v1/trips/lookup", {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          credentials: "omit",
          body: JSON.stringify(lookupBody(data)),
        });
        if (response.status !== 200) {
          this.error = LOOKUP_ERRORS[response.status] ?? UNAVAILABLE;
          return;
        }
        this.trip = tripView(await response.json());
        this.loaded = true;
      } catch {
        this.error = UNAVAILABLE;
      } finally {
        this.busy = false;
      }
    },
  }));

  window.Alpine.data("connection", () => ({
    state: "checking",

    get message() {
      return MESSAGES[this.state];
    },

    async init() {
      try {
        const response = await fetch("/api/v1/ping", {
          headers: { Accept: "application/json" },
          credentials: "omit",
        });
        this.state = stateFor(response.status);
      } catch {
        this.state = "unavailable";
      }
    },
  }));
});
