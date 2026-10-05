// On-Call Hero UI — vanilla JS + Alpine components

function onCallHero() {
  return {
    selected: null,
    state: null,
    timeline: [],
    incidents: [],
    scenarios: {},
    world: {},
    model: "unknown",
    scripted: false,
    fallback: false,
    workerOffline: false,
    chaosActive: false,
    temporalDown: false,
    chaos: { tool_error_rate: 0, tool_latency_ms: 0, llm_garbage_rate: 0 },
    noteText: "",
    validatorError: "",
    postmortem: "",
    countdown: "",
    phases: ["TRIAGE","INVESTIGATE","PROPOSE","AWAITING_APPROVAL","EXECUTE","VERIFY","ROLLBACK","RESOLVED"],

    async init() {
      await this.loadScenarios();
      await this.refresh();
      setInterval(() => this.refresh(), 1000);
      this.listenStack();
      this.listenChaos();
    },

    async loadScenarios() {
      try {
        const resp = await fetch("/api/scenarios");
        const data = await resp.json();
        this.scenarios = data.scenarios;
      } catch (e) { console.error(e); }
    },

    async refresh() {
      await this.loadIncidents();
      if (this.selected) {
        await this.loadIncident();
        this.updateCountdown();
      }
      await this.loadWorld();
    },

    async loadIncidents() {
      try {
        const resp = await fetch("/api/incidents");
        const data = await resp.json();
        this.incidents = data.incidents;
        if (!this.selected && this.incidents.length) {
          this.selected = this.incidents[0].workflow_id;
        }
      } catch (e) { this.temporalDown = true; }
    },

    async loadIncident() {
      try {
        const resp = await fetch(`/api/incidents/${this.selected}`);
        const data = await resp.json();
        this.state = data.state;
        this.timeline = data.history;
        this.workerOffline = data.worker_online === false;
        this.validatorError = "";
        if (this.state?.postmortem) {
          await this.loadPostmortem();
        }
      } catch (e) { this.temporalDown = true; }
    },

    async loadPostmortem() {
      try {
        const resp = await fetch(`/api/incidents/${this.selected}/postmortem`);
        const data = await resp.json();
        this.postmortem = data.markdown;
      } catch (e) { /* not written yet */ }
    },

    async loadWorld() {
      try {
        const resp = await fetch("/api/stack/metrics");
        if (resp.ok) this.world = await resp.json();
        else this.world = {};
      } catch (e) { /* world endpoint not available */ }
    },

    async trigger(id) {
      try {
        await fetch(`/api/scenarios/${id}/trigger`, { method: "POST" });
        setTimeout(() => this.refresh(), 500);
      } catch (e) { console.error(e); }
    },

    async reset() {
      await fetch("/api/scenarios/reset", { method: "POST" });
      await this.loadWorld();
    },

    select(id) {
      this.selected = id;
      this.postmortem = "";
      this.loadIncident();
    },

    async approve() {
      try {
        const steps = this.state?.plan?.steps ?? [];
        const resp = await fetch(`/api/incidents/${this.selected}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps, comment: "approved from UI" }),
        });
        if (!resp.ok) {
          const err = await resp.json();
          this.validatorError = err.detail;
        } else {
          this.validatorError = "";
          setTimeout(() => this.refresh(), 300);
        }
      } catch (e) { console.error(e); }
    },

    async reject() {
      try {
        await fetch(`/api/incidents/${this.selected}/reject`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "rejected from UI" }),
        });
        setTimeout(() => this.refresh(), 300);
      } catch (e) { console.error(e); }
    },

    async sendPause() { await fetch(`/api/incidents/${this.selected}/pause`, { method: "POST" }); },
    async sendResume() { await fetch(`/api/incidents/${this.selected}/resume`, { method: "POST" }); },
    async sendCancel() { await fetch(`/api/incidents/${this.selected}/cancel`, { method: "POST" }); },
    async sendNote() {
      if (!this.noteText.trim()) return;
      try {
        await fetch(`/api/incidents/${this.selected}/note`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: this.noteText.trim() }),
        });
        this.noteText = "";
        await this.refresh();
      } catch (e) { console.error("Note failed:", e); }
    },

    removeStep(i) {
      if (this.state?.plan?.steps) {
        this.state.plan.steps.splice(i, 1);
      }
    },

    async setChaos() {
      await fetch("/api/chaos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.chaos),
      });
    },

    async preset(name) {
      await fetch(`/api/chaos/preset/${name}`, { method: "POST" });
      const resp = await fetch("/api/chaos");
      this.chaos = await resp.json();
    },

    async clearChaos() {
      this.chaos = { tool_error_rate: 0, tool_latency_ms: 0, llm_garbage_rate: 0 };
      await this.setChaos();
    },

    listenStack() {
      const es = new EventSource("/api/stack/events");
      es.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.worker) {
          this.workerOffline = !data.worker.running;
        }
      };
    },

    listenChaos() {
      fetch("/api/chaos").then(r => r.json()).then(c => {
        this.chaos = c;
        this.chaosActive = (c.tool_error_rate > 0) || (c.tool_latency_ms > 0) || (c.llm_garbage_rate > 0);
      });
    },

    updateCountdown() {
      if (this.state?.phase !== "AWAITING_APPROVAL") {
        this.countdown = "";
        return;
      }
      // Simple countdown display; real escalation timer lives in the workflow.
      this.countdown = "waiting for human…";
    },
  };
}

function servicePills() {
  return {
    status: {},
    openMenu: null,
    async init() {
      setInterval(() => this.refresh(), 1000);
      this.refresh();
    },
    async refresh() {
      try {
        const resp = await fetch("/api/stack");
        this.status = await resp.json();
      } catch (e) { /* gateway down */ }
    },
    menu(svc) { this.openMenu = this.openMenu === svc ? null : svc; },
    async action(svc, act) {
      await fetch(`/api/services/${svc}/${act}`, { method: "POST" });
      this.openMenu = null;
      setTimeout(() => this.refresh(), 300);
    },
    async tail(svc) {
      const resp = await fetch(`/api/services/${svc}/logs?n=50`);
      const data = await resp.json();
      alert(data.logs || "(no logs)");
      this.openMenu = null;
    },
    uptime(svc) {
      const s = this.status[svc];
      if (!s?.uptime_s) return "";
      const m = Math.floor(s.uptime_s / 60);
      const sec = Math.floor(s.uptime_s % 60);
      return `${m}m ${sec}s`;
    },
  };
}

function scenarioPanel() {
  return {
    triggering: false,
    async trigger(id) {
      this.triggering = true;
      try {
        await fetch(`/api/scenarios/${id}/trigger`, { method: "POST" });
      } finally {
        this.triggering = false;
      }
    },
    async reset() {
      await fetch("/api/scenarios/reset", { method: "POST" });
    },
  };
}
