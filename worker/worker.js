// Slack slash command -> GitHub repository_dispatch 중계 Worker.
// Slack은 3초 안에 응답을 요구하므로, dispatch를 보내고 즉시 ack를 돌려준다.

const PERIODS = ["daily", "weekly", "monthly"];

async function verifySlack(request, body, signingSecret) {
  const ts = request.headers.get("x-slack-request-timestamp");
  const sig = request.headers.get("x-slack-signature");
  if (!ts || !sig) return false;
  // 5분 이상 지난 요청은 replay로 간주
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

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("ok");

    const body = await request.text();
    if (!(await verifySlack(request, body, env.SLACK_SIGNING_SECRET))) {
      return new Response("invalid signature", { status: 401 });
    }

    const params = new URLSearchParams(body);
    const arg = (params.get("text") || "").trim().toLowerCase();
    const period = PERIODS.includes(arg) ? arg : "daily";

    const resp = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
      {
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
      },
    );

    const text = resp.ok
      ? `:hourglass_flowing_sand: ${period} trending digest를 생성 중입니다. 잠시 후 이 채널에 도착합니다.`
      : `:warning: GitHub dispatch 실패 (${resp.status}). 워크플로우/PAT를 확인해 주세요.`;

    return new Response(
      JSON.stringify({ response_type: "ephemeral", text }),
      { headers: { "Content-Type": "application/json" } },
    );
  },
};
