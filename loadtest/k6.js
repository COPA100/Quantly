// k6 load test for quantly. pick a scenario with -e SCENARIO=steady|ramp|burst.
// see loadtest/README.md for the full list of env vars and how to run it.
import http from "k6/http";
import exec from "k6/execution";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const env = (name, fallback) => (__ENV[name] !== undefined ? __ENV[name] : fallback);

const BASE_URL = env("BASE_URL", "http://localhost:8000");
const SCENARIO = env("SCENARIO", "steady");
const USERS = parseInt(env("USERS", "20"));
const PASSWORD = env("PASSWORD", "loadtest-password");
const EMAIL_PREFIX = env("EMAIL_PREFIX", "load");
// pause between setup logins, so the per-ip login limit is not hit. 0 when the
// limit env is set high for the run.
const LOGIN_PAUSE = parseFloat(env("LOGIN_PAUSE", "0"));
// warm: every upload is the sample book (analytics cache hits after the first).
// cold: every upload is a unique book over a ticker pool, so nothing is cached.
const BOOK = env("BOOK", "warm");
const TICKER_POOL = parseInt(env("TICKER_POOL", "200"));
const BOOK_SIZE = parseInt(env("BOOK_SIZE", "8"));
const WORKERS = parseInt(env("WORKERS", "1"));
const SUMMARY_PATH = env("SUMMARY_PATH", `/work/loadtest/results/${SCENARIO}.json`);

// steady
const RATE = parseInt(env("RATE", "5")); // uploads per second
const DURATION = env("DURATION", "2m");
const READ_RATIO = parseFloat(env("READ_RATIO", "4")); // read requests per upload
// ramp
const RAMP_START = parseInt(env("RAMP_START", "2"));
const RAMP_PEAK = parseInt(env("RAMP_PEAK", "60"));
const RAMP_DURATION = env("RAMP_DURATION", "5m");
// burst
const BURST_UPLOADS = parseInt(env("BURST_UPLOADS", "200"));
const BURST_WITHIN = env("BURST_WITHIN", "10s");
const POLL_INTERVAL = parseFloat(env("POLL_INTERVAL", "1"));
const DRAIN_TIMEOUT_S = parseInt(env("DRAIN_TIMEOUT_S", "900"));

const SAMPLE = open("../example_csv/ex1.csv", "b");
const HEADER = `"Positions for account Individual ...902 as of 03:18 PM ET, 2025/12/31"\n\n"Symbol","Description","Qty (Quantity)","Price","Cost Basis"\n`;
const FOOTER = `"Cash & Cash Investments","--","--","--","$8.35"\n"Account Total","","--","--","$50.85"\n`;

const uploadsAccepted = new Counter("uploads_accepted");
const jobsComplete = new Counter("jobs_complete");
const jobsFailed = new Counter("jobs_failed");
const jobsTimedOut = new Counter("jobs_timed_out");
// ms from accept to a terminal status, as seen by polling
const timeToComplete = new Trend("time_to_complete_ms", true);
// ms from the start of the burst to each completion, the max is the drain time
const completedAt = new Trend("completed_at_ms", true);

function status(name) {
  return { name };
}

const scenarios = {
  steady: {
    uploads: {
      executor: "constant-arrival-rate",
      exec: "upload",
      rate: RATE,
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.max(10, RATE * 2),
      maxVUs: Math.max(50, RATE * 10),
    },
    reads: {
      executor: "constant-arrival-rate",
      exec: "read",
      rate: Math.max(1, Math.round(RATE * READ_RATIO)),
      timeUnit: "1s",
      duration: DURATION,
      preAllocatedVUs: Math.max(10, RATE * 2),
      maxVUs: Math.max(50, RATE * 10),
    },
  },
  ramp: {
    ramp: {
      executor: "ramping-arrival-rate",
      exec: "mixed",
      startRate: RAMP_START,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [{ target: RAMP_PEAK, duration: RAMP_DURATION }],
    },
  },
  burst: {
    burst: {
      executor: "shared-iterations",
      exec: "burst",
      vus: Math.min(BURST_UPLOADS, 100),
      iterations: BURST_UPLOADS,
      maxDuration: `${DRAIN_TIMEOUT_S + 120}s`,
    },
  },
};

// thresholds come from docs/slo.md: upload accept p99 under 300 ms, 99.9% of
// requests not failing. the ramp aborts once they break, that is the point.
const thresholds = {
  "http_req_duration{name:upload}": [
    { threshold: "p(99)<300", abortOnFail: SCENARIO === "ramp", delayAbortEval: "30s" },
  ],
  http_req_failed: [
    { threshold: "rate<0.001", abortOnFail: SCENARIO === "ramp", delayAbortEval: "30s" },
  ],
};
if (SCENARIO === "steady") {
  thresholds["http_req_duration{name:status}"] = ["p(95)<500"];
  thresholds["http_req_duration{name:analytics}"] = ["p(95)<500"];
}
if (SCENARIO === "burst") {
  thresholds["jobs_failed"] = ["count==0"];
  thresholds["jobs_timed_out"] = ["count==0"];
}

export const options = {
  scenarios: scenarios[SCENARIO],
  thresholds,
  setupTimeout: "10m",
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

function json(token) {
  return { headers: { Authorization: `Bearer ${token}` } };
}

function csvBody(seed) {
  if (BOOK === "warm") return SAMPLE;
  // unique ticker set per upload: stable names so the mock source is deterministic
  const rows = [];
  const used = new Set();
  let s = seed;
  while (used.size < BOOK_SIZE) {
    s = (s * 1103515245 + 12345) % 2147483648;
    used.add(`LT${String(s % TICKER_POOL).padStart(4, "0")}`);
  }
  for (const t of used) {
    const qty = 1 + (s % 50);
    rows.push(`"${t}","LOAD ${t}","${qty}","$10.00","$${(qty * 10).toFixed(2)}"\n`);
    s = (s * 1103515245 + 12345) % 2147483648;
  }
  return HEADER + rows.join("") + FOOTER;
}

function uploadBook(token, seed) {
  const file = http.file(csvBody(seed), "load.csv", "text/csv");
  const res = http.post(`${BASE_URL}/portfolios`, { file }, { ...json(token), tags: status("upload") });
  const ok = check(res, { "upload 202": (r) => r.status === 202 });
  if (!ok) return null;
  uploadsAccepted.add(1);
  return res.json("id");
}

export function setup() {
  const users = [];
  for (let i = 0; i < USERS; i++) {
    const email = `${EMAIL_PREFIX}${i}@loadtest.example`;
    const body = JSON.stringify({ email, password: PASSWORD });
    const type = { headers: { "Content-Type": "application/json" } };
    // 409 means a previous run already registered this user
    const reg = http.post(`${BASE_URL}/auth/register`, body, { ...type, tags: status("setup") });
    if (reg.status !== 201 && reg.status !== 409) {
      exec.test.abort(`register failed: ${reg.status} ${reg.body}`);
    }
    const login = http.post(`${BASE_URL}/auth/login`, body, { ...type, tags: status("setup") });
    if (login.status !== 200) {
      exec.test.abort(
        `login failed: ${login.status}. raise QUANTLY_RATE_LIMIT_LOGIN_MAX or set LOGIN_PAUSE`
      );
    }
    const token = login.json("access_token");
    // one finished-or-queued portfolio per user for the read scenarios. it goes
    // through the same upload path, and is not tagged as load.
    let id = null;
    if (SCENARIO !== "burst") {
      const file = http.file(SAMPLE, "seed.csv", "text/csv");
      const res = http.post(`${BASE_URL}/portfolios`, { file }, { ...json(token), tags: status("setup") });
      id = res.status === 202 ? res.json("id") : null;
    }
    users.push({ token, portfolioId: id });
    if (LOGIN_PAUSE > 0) sleep(LOGIN_PAUSE);
  }
  // access tokens last 15 minutes by default, keep runs shorter or raise
  // QUANTLY_ACCESS_TOKEN_EXPIRE_MINUTES
  return { users, startedAt: Date.now() };
}

function pick(data) {
  return data.users[exec.vu.idInTest % data.users.length];
}

export function upload(data) {
  const user = data.users[exec.scenario.iterationInTest % data.users.length];
  uploadBook(user.token, exec.scenario.iterationInTest + 1);
}

export function read(data) {
  const user = pick(data);
  if (user.portfolioId === null) return;
  const base = `${BASE_URL}/portfolios/${user.portfolioId}`;
  const which = exec.scenario.iterationInTest % 3;
  if (which === 0) {
    http.get(base, { ...json(user.token), tags: status("portfolio") });
  } else if (which === 1) {
    http.get(`${base}/status`, { ...json(user.token), tags: status("status") });
  } else {
    http.get(`${base}/analytics`, { ...json(user.token), tags: status("analytics") });
  }
}

// ramp: one upload per READ_RATIO reads, so the mix matches steady
export function mixed(data) {
  if (exec.scenario.iterationInTest % (READ_RATIO + 1) === 0) upload(data);
  else read(data);
}

// upload, then poll status until the job is terminal
export function burst(data) {
  const user = data.users[exec.scenario.iterationInTest % data.users.length];
  const t0 = Date.now();
  const id = uploadBook(user.token, exec.scenario.iterationInTest + 1);
  if (id === null) return;
  for (;;) {
    const res = http.get(`${BASE_URL}/portfolios/${id}/status`, {
      ...json(user.token),
      tags: status("status"),
    });
    const state = res.status === 200 ? res.json("status") : null;
    if (state === "complete" || state === "failed") {
      const now = Date.now();
      timeToComplete.add(now - t0);
      completedAt.add(now - data.startedAt);
      (state === "complete" ? jobsComplete : jobsFailed).add(1);
      return;
    }
    if ((Date.now() - t0) / 1000 > DRAIN_TIMEOUT_S) {
      jobsTimedOut.add(1);
      return;
    }
    sleep(POLL_INTERVAL);
  }
}

// a flat json file that loadtest/capacity.py reads, plus the usual text summary
export function handleSummary(data) {
  const m = {};
  for (const [name, metric] of Object.entries(data.metrics)) m[name] = metric.values;
  const out = {
    scenario: SCENARIO,
    book: BOOK,
    workers: WORKERS,
    test_duration_ms: data.state.testRunDurationMs,
    options: { RATE, BURST_UPLOADS, USERS },
    thresholds_passed: Object.values(data.metrics).every(
      (metric) => !metric.thresholds || Object.values(metric.thresholds).every((t) => t.ok)
    ),
    metrics: m,
  };
  return {
    [SUMMARY_PATH]: JSON.stringify(out, null, 2),
    stdout: textSummary(m),
  };
}

function textSummary(m) {
  const line = (label, v) => `${label.padEnd(34)}${v}\n`;
  const t = (key) => m[`http_req_duration{name:${key}}`];
  let s = "\nquantly load test summary\n";
  const up = t("upload");
  if (up) {
    s += line("upload p50/p95/p99 (ms)", `${up.med.toFixed(0)} / ${up["p(95)"].toFixed(0)} / ${up["p(99)"].toFixed(0)}`);
  }
  if (m.http_reqs) s += line("requests/s", m.http_reqs.rate.toFixed(1));
  if (m.http_req_failed) s += line("error rate", (m.http_req_failed.rate * 100).toFixed(2) + "%");
  if (m.completed_at_ms) s += line("time to drain (s)", (m.completed_at_ms.max / 1000).toFixed(1));
  if (m.jobs_complete) s += line("jobs complete", m.jobs_complete.count);
  return s;
}
