export async function onRequest(context) {
  const { request, env } = context;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  if (request.method === "GET") {
    return new Response(JSON.stringify({
      status: "online",
      env_check: {
        POLAR_TOKEN: env.POLAR_ACCESS_TOKEN ? "OK" : "MISSING",
        SUPABASE_KEY: env.SUPABASE_SERVICE_ROLE_KEY ? "OK" : "MISSING",
        SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "OK" : "MISSING",
      }
    }), { headers: corsHeaders });
  }

  if (request.method === "POST") {
    try {
      const { user_id } = await request.json();
      const { POLAR_ACCESS_TOKEN, SUPABASE_SERVICE_ROLE_KEY, NEXT_PUBLIC_SUPABASE_URL } = env;

      if (!POLAR_ACCESS_TOKEN || !SUPABASE_SERVICE_ROLE_KEY || !NEXT_PUBLIC_SUPABASE_URL) {
        throw new Error("Missing environment variables");
      }

      // 1. Get Polar Sub ID from Supabase
      const subRes = await fetch(`${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}&select=polar_subscription_id`, {
        headers: { "apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}` }
      });
      const subData = await subRes.json();
      const polarSubId = subData?.[0]?.polar_subscription_id;

      if (!polarSubId) throw new Error("No subscription found to cancel.");

      // 2. Revoke in Polar
      const polarRevoke = await fetch(`https://api.polar.sh/v1/subscriptions/${polarSubId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}` }
      });
      if (!polarRevoke.ok) throw new Error("Polar revocation failed");

      // 3. Update Supabase
      await fetch(`${NEXT_PUBLIC_SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}`, {
        method: "PATCH",
        headers: {
          "apikey": SUPABASE_SERVICE_ROLE_KEY,
          "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ status: "canceled", updated_at: new Date().toISOString() })
      });

      return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: corsHeaders });
}
