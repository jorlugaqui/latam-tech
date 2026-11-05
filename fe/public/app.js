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

// ---- recommendation and human case (specs passenger-web, recommendation, human-handoff)
// The page only renders what the API decided. Follow-up calls resend the booking code and
// surname of the current lookup from memory (never stored); the server re-verifies both.

const ENTITLEMENT_TEXT = {
  REBOOK_NO_FEE: "Rebook at no fee",
  PRIORITY_HANDLING: "Priority handling, reviewed by an agent",
  MEAL_VOUCHER: "Meal voucher",
  CASH_COMPENSATION: "Cash compensation, reviewed by an agent",
};
const CASE_ERRORS = {
  option_not_eligible: "This option is no longer available. Please check your options again.",
  nothing_to_escalate: "There is nothing to hand to an agent for this trip.",
};
const CASE_UNAVAILABLE =
  "We couldn't send your request right now. Please try again or contact the call center.";

function recoView(body) {
  return {
    headline: body.explanation.headline,
    details: body.explanation.details,
    proposed: body.status === "PROPOSED",
    entitlements: body.entitlements.map((e) => ({
      key: e.rule_id,
      text: `${ENTITLEMENT_TEXT[e.code] ?? e.code} (rule ${e.rule_id}, ${body.policy_version})`,
    })),
    options: body.options.map((o) => ({
      key: o.option_id,
      id: o.option_id,
      title: `${o.flight_number} ${o.origin} → ${o.destination}`,
      departure: o.departure
        ? `Departs ${localTime(o.departure, o.origin)} on ${o.departure.slice(0, 10)}`
        : "",
      fare: o.fare_difference ? `Fare difference: ${o.fare_difference} ${o.currency ?? ""}` : "No fare difference",
    })),
  };
}

const EMPTY_RECO = { headline: "", details: [], proposed: false, entitlements: [], options: [] };
const EMPTY_CASE = { open: false, title: "", message: "" };

function caseView(body) {
  return {
    open: body.status === "OPEN",
    title: body.status === "OPEN" ? `Case ${body.case_id}` : "Request being registered",
    message: body.message,
  };
}

async function postJson(url, body) {
  return fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    credentials: "omit",
    body: JSON.stringify(body),
  });
}

document.addEventListener("alpine:init", () => {
  window.Alpine.data("tripLookup", () => ({
    busy: false,
    error: "",
    trip: EMPTY_TRIP,
    loaded: false,
    current: null, // {booking_id, last_name} of the shown trip: memory only
    reco: EMPTY_RECO,
    recoLoaded: false,
    caseInfo: EMPTY_CASE,
    caseLoaded: false,

    get hasError() {
      return this.error !== "";
    },
    get hasTrip() {
      return this.loaded;
    },
    get showOptions() {
      return (
        this.loaded && this.trip.nextStep === "RECOMMENDATION" && !this.recoLoaded && !this.caseLoaded
      );
    },
    get showAgent() {
      return this.loaded && this.trip.nextStep === "HUMAN_ASSISTANCE" && !this.caseLoaded;
    },
    get hasReco() {
      return this.recoLoaded && !this.caseLoaded;
    },
    get recoProposed() {
      return this.recoLoaded && this.reco.proposed;
    },
    get recoNeedsAgent() {
      return this.recoLoaded && !this.reco.proposed;
    },
    get hasCase() {
      return this.caseLoaded;
    },

    // The CSP build calls handlers with the event. Values come from the form itself
    // (x-model does not work in the CSP build) and live only for this request.
    async submit(event) {
      const form = event?.target instanceof HTMLFormElement ? event.target : this.$refs.form;
      const data = new FormData(form);
      const body = lookupBody(data);
      this.busy = true;
      this.error = "";
      this.loaded = false;
      this.current = null;
      this.reco = EMPTY_RECO;
      this.recoLoaded = false;
      this.caseInfo = EMPTY_CASE;
      this.caseLoaded = false;
      try {
        const response = await postJson("/api/v1/trips/lookup", body);
        if (response.status !== 200) {
          this.error = LOOKUP_ERRORS[response.status] ?? UNAVAILABLE;
          return;
        }
        this.trip = tripView(await response.json());
        this.current = body;
        this.loaded = true;
      } catch {
        this.error = UNAVAILABLE;
      } finally {
        this.busy = false;
      }
    },

    async seeOptions() {
      await this.call("/api/v1/trips/recommendation", this.current, async (response) => {
        this.reco = recoView(await response.json());
        this.recoLoaded = true;
      });
    },

    // The CSP build cannot pass arguments: the option id comes from the clicked button.
    async requestOption(event) {
      const optionId = event?.target?.closest("button")?.dataset.option;
      if (!optionId) return;
      await this.openCase({ ...this.current, option_id: optionId });
    },

    async talkToAgent() {
      await this.openCase({ ...this.current });
    },

    async openCase(body) {
      await this.call("/api/v1/trips/human-case", body, async (response) => {
        this.caseInfo = caseView(await response.json());
        this.caseLoaded = true;
      });
    },

    async call(url, body, onSuccess) {
      if (!this.current || this.busy) return;
      this.busy = true;
      this.error = "";
      try {
        const response = await postJson(url, body);
        if ([200, 201, 202].includes(response.status)) {
          await onSuccess(response);
        } else if (response.status === 409) {
          const problem = await response.json().catch(() => ({}));
          this.error = CASE_ERRORS[problem.error] ?? CASE_UNAVAILABLE;
        } else if (response.status === 503 && url.endsWith("human-case")) {
          this.error = CASE_UNAVAILABLE;
        } else {
          this.error = LOOKUP_ERRORS[response.status] ?? UNAVAILABLE;
        }
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
