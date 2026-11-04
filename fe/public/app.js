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

document.addEventListener("alpine:init", () => {
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
