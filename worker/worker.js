// Slack slash command + 버튼 interaction -> GitHub repository_dispatch 중계 Worker.
// Slack은 3초 안에 응답을 요구하므로, dispatch를 보내고 즉시 ack를 돌려준다.

const PERIODS = ["daily", "weekly", "monthly", "yearly", "rising"];
const LABELS = {
  daily: "일간",
  weekly: "주간",
  monthly: "월간",
  yearly: "연간 (1년 내 신생)",
  rising: "빠른 성장 (30일 내 신생)",
};

async function verifySlack(request, body, signingSecret) {
  const ts = request.headers.get("x-slack-request-timestamp");
  const sig = request.headers.get("x-slack-signature");
  if (!ts || !sig) return false;
  if (Math.abs(Date.now() / 1000 - Number(ts)) > 300) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(signingSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`v0:${ts}:${body}`),
  );
  const computed =
    "v0=" +
    [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return computed === sig;
}

function menu() {
  return new Response(
    JSON.stringify({
      response_type: "ephemeral",
      text: "GitHub Trending — 어떤 digest를 볼까요?",
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*GitHub Trending* — 어떤 기간의 digest를 볼까요?",
          },
        },
        {
          type: "actions",
          elements: PERIODS.map((p) => ({
            type: "button",
            text: { type: "plain_text", text: LABELS[p] },
            value: p,
          })),
        },
      ],
    }),
    { headers: { "Content-Type": "application/json" } },
  );
}

async function dispatch(env, period) {
  return fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "github-trend-worker",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      event_type: "trending-request",
      client_payload: { period },
    }),
  });
}

function ack(text, replace) {
  return new Response(
    JSON.stringify({
      response_type: "ephemeral",
      ...(replace ? { replace_original: true } : {}),
      text,
    }),
    { headers: { "Content-Type": "application/json" } },
  );
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("ok");

    const body = await request.text();
    if (!(await verifySlack(request, body, env.SLACK_SIGNING_SECRET))) {
      return new Response("invalid signature", { status: 401 });
    }

    const params = new URLSearchParams(body);

    // 버튼 클릭 (interactivity payload)
    if (params.has("payload")) {
      let period = "daily";
      try {
        const pl = JSON.parse(params.get("payload"));
        const v = pl?.actions?.[0]?.value;
        if (PERIODS.includes(v)) period = v;
      } catch {}
      const resp = await dispatch(env, period);
      return ack(
        resp.ok
          ? `:hourglass_flowing_sand: ${LABELS[period]} digest를 생성 중입니다. 잠시 후 이 채널에 도착합니다.`
          : `:warning: GitHub dispatch 실패 (${resp.status}). 워크플로우/PAT를 확인해 주세요.`,
        true,
      );
    }

    // slash command: 인자가 없거나 모르는 인자면 선택지 표시
    const arg = (params.get("text") || "").trim().toLowerCase();
    if (!PERIODS.includes(arg)) return menu();

    const resp = await dispatch(env, arg);
    return ack(
      resp.ok
        ? `:hourglass_flowing_sand: ${LABELS[arg]} digest를 생성 중입니다. 잠시 후 이 채널에 도착합니다.`
        : `:warning: GitHub dispatch 실패 (${resp.status}). 워크플로우/PAT를 확인해 주세요.`,
    );
  },
};
