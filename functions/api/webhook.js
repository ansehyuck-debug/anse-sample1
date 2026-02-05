export async function onRequest(context) {
  const { request, env } = context;

  if (request.method === "OPTIONS") {
    return new Response(null, { 
      status: 204, 
      headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS" } 
    });
  }

  if (request.method === "GET") {
    return new Response("Webhook endpoint is active. Please use POST.", { status: 200 });
  }

  if (request.method === "POST") {
    try {
      const { SUPABASE_SERVICE_ROLE_KEY, NEXT_PUBLIC_SUPABASE_URL } = env;
      const payload = await request.json();
      const { type, data } = payload;

      console.log(`Webhook Event: ${type}`);

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
      console.error("Webhook Error:", err.message);
      return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
  }

  return new Response("Method not allowed", { status: 405 });
}
