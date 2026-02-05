export async function onRequestGet(context) {
  const { env } = context;
  const health = {
    endpoint: "webhook",
    env_status: {
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
  const SUPABASE_SERVICE_ROLE_KEY = env.SUPABASE_SERVICE_ROLE_KEY;
  const SUPABASE_URL = env.NEXT_PUBLIC_SUPABASE_URL;

  try {
    if (!SUPABASE_SERVICE_ROLE_KEY || !SUPABASE_URL) {
      throw new Error("Webhook Error: Missing Supabase environment variables.");
    }

    const payload = await request.json();
    const type = payload.type;
    const data = payload.data;

    console.log(`Webhook Event: ${type}`);

    if (type === "order.paid" || type === "subscription.created" || type === "subscription.active") {
      const userId = data.metadata?.supabase_user_id || data.subscription?.metadata?.supabase_user_id;
      const subId = data.subscription_id || data.id;

      if (userId && subId) {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/subscriptions`, {
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
        if (!response.ok) console.error("Webhook Supabase Write Error:", await response.text());
      }
    }

    if (type === "subscription.revoked" || type === "subscription.canceled") {
      const subId = data.id;
      await fetch(`${SUPABASE_URL}/rest/v1/subscriptions?polar_subscription_id=eq.${subId}`, {
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
    console.error("Webhook Fatal Error:", err.message);
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}