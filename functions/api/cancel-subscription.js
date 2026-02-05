export async function onRequestGet(context) {
  const { env } = context;
  const health = {
    endpoint: "cancel-subscription",
    env_status: {
      POLAR_ACCESS_TOKEN: env.POLAR_ACCESS_TOKEN ? "Set" : "Missing",
      SUPABASE_SERVICE_ROLE_KEY: env.SUPABASE_SERVICE_ROLE_KEY ? "Set" : "Missing",
      NEXT_PUBLIC_SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "Set" : "Missing",
    }
  };
  return new Response(JSON.stringify(health, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
}

export async function onRequestPost(context) {
  const { env, request } = context;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
  };

  try {
    const missingVars = [];
    if (!env.POLAR_ACCESS_TOKEN) missingVars.push("POLAR_ACCESS_TOKEN");
    if (!env.SUPABASE_SERVICE_ROLE_KEY) missingVars.push("SUPABASE_SERVICE_ROLE_KEY");
    if (!env.NEXT_PUBLIC_SUPABASE_URL) missingVars.push("NEXT_PUBLIC_SUPABASE_URL");

    if (missingVars.length > 0) {
      throw new Error(`Configuration Error: Missing ${missingVars.join(", ")}`);
    }

    const { user_id } = await request.json();

    // 1. Supabase에서 구독 ID 조회
    const { data: subData } = await fetch(`${env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}&select=polar_subscription_id`, {
      headers: {
        "apikey": env.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`
      }
    }).then(r => r.json());

    const polarSubId = subData?.[0]?.polar_subscription_id;
    if (!polarSubId) throw new Error("Active Polar Subscription ID not found in database.");

    // 2. Polar에서 구독 취소
    const polarRevoke = await fetch(`https://api.polar.sh/v1/subscriptions/${polarSubId}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${env.POLAR_ACCESS_TOKEN}` }
    });

    if (!polarRevoke.ok) throw new Error("Failed to revoke subscription at Polar API.");

    // 3. Supabase 상태 업데이트
    await fetch(`${env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}`, {
      method: "PATCH",
      headers: {
        "apikey": env.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ status: "canceled", updated_at: new Date().toISOString() })
    });

    return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
  } catch (err) {
    console.error("Cancel API Error:", err.message);
    return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
  }
}