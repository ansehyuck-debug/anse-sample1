export async function onRequestPost(context) {
  const { env, request } = context;
  const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
  const SUPABASE_URL = env.NEXT_PUBLIC_SUPABASE_URL;
  const SUPABASE_SERVICE_KEY = env.SUPABASE_SERVICE_ROLE_KEY;

  try {
    const { user_id } = await request.json();

    // 1. Supabase에서 해당 유저의 구독 ID 가져오기
    const subQuery = await fetch(`${SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}&select=polar_subscription_id`, {
      headers: {
        "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`,
        "apikey": SUPABASE_SERVICE_KEY
      }
    });
    
    const subData = await subQuery.json();
    const polar_subscription_id = subData[0]?.polar_subscription_id;

    if (!polar_subscription_id) {
      return new Response(JSON.stringify({ error: "Active subscription not found" }), { status: 404 });
    }

    // 2. Polar API 호출하여 구독 취소
    // Ref: polar.txt -> delete /v1/subscriptions/{id} (Revoke)
    const response = await fetch(`https://api.polar.sh/v1/subscriptions/${polar_subscription_id}`, {
      method: "DELETE",
      headers: {
        "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`,
        "Accept": "application/json"
      }
    });

    if (!response.ok) {
      const err = await response.json();
      return new Response(JSON.stringify({ error: err.detail || "Failed to cancel subscription" }), { status: response.status });
    }

    // 3. Supabase 상태 즉시 업데이트 (Webhook이 오겠지만 즉각 반영을 위해)
    await fetch(`${SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${user_id}`, {
      method: "PATCH",
      headers: {
        "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`,
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ status: 'canceled', updated_at: new Date().toISOString() })
    });

    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json" }
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}
