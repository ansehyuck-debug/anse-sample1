export async function onRequest(context) {
  const { request, env } = context;
  const { POLAR_WEBHOOK_SECRET, SUPABASE_SERVICE_ROLE_KEY, NEXT_PUBLIC_SUPABASE_URL } = env;

  if (request.method === "OPTIONS") {
    return new Response(null, { 
      status: 204, 
      headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS" } 
    });
  }

  if (request.method === "GET") {
    return new Response(JSON.stringify({
      status: "online",
      endpoint: "webhook",
      env_check: {
        WEBHOOK_SECRET: POLAR_WEBHOOK_SECRET ? "Set" : "Missing",
        SUPABASE_KEY: SUPABASE_SERVICE_ROLE_KEY ? "Set" : "Missing"
      }
    }), { headers: { "Content-Type": "application/json" } });
  }

  if (request.method === "POST") {
    try {
      // 1. 보안 검증 (Webhook Signature Validation)
      // Polar(Standard Webhooks)는 webhook-id, webhook-timestamp, webhook-signature 헤더를 보냅니다.
      const webhookId = request.headers.get("webhook-id");
      const webhookTimestamp = request.headers.get("webhook-timestamp");
      const webhookSignature = request.headers.get("webhook-signature");

      if (!webhookId || !webhookTimestamp || !webhookSignature) {
        console.error("Missing webhook headers");
        return new Response("Missing headers", { status: 401 });
      }

      const bodyText = await request.text();
      
      // Secret이 설정되어 있다면 검증 수행
      if (POLAR_WEBHOOK_SECRET) {
        // Standard Webhooks 검증 로직: msg_id + "." + timestamp + "." + body
        const signedContent = `${webhookId}.${webhookTimestamp}.${bodyText}`;
        const encoder = new TextEncoder();
        const key = await crypto.subtle.importKey(
          "raw",
          encoder.encode(POLAR_WEBHOOK_SECRET.startsWith('whsec_') ? POLAR_WEBHOOK_SECRET.substring(6) : POLAR_WEBHOOK_SECRET),
          { name: "HMAC", hash: "SHA-256" },
          false,
          ["verify"]
        );

        // Polar는 v1,sig1 형식으로 보낼 수 있으므로 sig1 부분만 추출
        const signatures = webhookSignature.split(' ').map(s => s.split(',')[1]);
        let isValid = false;

        for (const sig of signatures) {
          const sigBytes = hexToBytes(sig);
          const result = await crypto.subtle.verify(
            "HMAC",
            key,
            sigBytes,
            encoder.encode(signedContent)
          );
          if (result) { isValid = true; break; }
        }

        if (!isValid) {
          console.error("Invalid webhook signature");
          return new Response("Invalid signature", { status: 401 });
        }
      }

      // 2. 데이터 처리
      const payload = JSON.parse(bodyText);
      const { type, data } = payload;
      console.log(`Verified Webhook Event: ${type}`);

      // 결제 완료/구독 시작 처리
      if (["order.paid", "subscription.created", "subscription.active"].includes(type)) {
        const userId = data.metadata?.supabase_user_id || data.subscription?.metadata?.supabase_user_id;
        const subId = data.subscription_id || data.id;

        if (userId && subId) {
          await fetch(`${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions`, {
            method: "POST",
            headers: {
              "apikey": SUPABASE_SERVICE_ROLE_KEY,
              "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
              "Content-Type": "application/json",
              "Prefer": "resolution=merge-duplicates"
            },
            body: JSON.stringify({
              user_id: userId,
              polar_subscription_id: subId,
              status: "active",
              updated_at: new Date().toISOString()
            })
          });
        }
      }

      // 구독 해지 처리
      if (["subscription.revoked", "subscription.canceled"].includes(type)) {
        const subId = data.id;
        await fetch(`${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions?polar_subscription_id=eq.${subId}`, {
          method: "PATCH",
          headers: {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ status: "inactive", updated_at: new Date().toISOString() })
        });
      }

      return new Response(JSON.stringify({ received: true }), { status: 200 });
    } catch (err) {
      console.error("Webhook Processing Error:", err.message);
      return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
  }

  return new Response("Method not allowed", { status: 405 });
}

// Hex string to Uint8Array helper
function hexToBytes(hex) {
  let bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
}