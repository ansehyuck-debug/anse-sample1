export async function onRequestPost(context) {
  const { env, request } = context;
  const SUPABASE_URL = env.NEXT_PUBLIC_SUPABASE_URL;
  const SUPABASE_SERVICE_KEY = env.SUPABASE_SERVICE_ROLE_KEY; // 사용자가 추가해야 함

  try {
    const payload = await request.json();
    const eventType = payload.type;
    const data = payload.data;

    console.log(`Received Polar Webhook: ${eventType}`);

    // metadata에서 유저 ID 추출 (create-checkout에서 넣은 값)
    // Polar의 webhook 구조에 따라 위치가 다를 수 있으나 보통 data.metadata에 위치
    const supabase_user_id = data.metadata?.supabase_user_id;

    if (!supabase_user_id) {
      console.warn("No supabase_user_id found in webhook metadata");
      return new Response("OK", { status: 200 });
    }

    let status = 'inactive';
    let polar_subscription_id = data.id;

    if (eventType === 'subscription.created' || eventType === 'subscription.active') {
      status = 'active';
    } else if (eventType === 'subscription.revoked' || eventType === 'subscription.canceled') {
      status = 'canceled';
    } else if (eventType === 'order.paid') {
      // 단건 결제 혹은 구독의 첫 결제
      status = 'active';
    }

    // Supabase DB 업데이트
    const updateResponse = await fetch(`${SUPABASE_URL}/rest/v1/subscriptions`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`,
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-upsert"
      },
      body: JSON.stringify({
        user_id: supabase_user_id,
        polar_subscription_id: polar_subscription_id,
        status: status,
        updated_at: new Date().toISOString()
      })
    });

    if (!updateResponse.ok) {
      const errText = await updateResponse.text();
      console.error("Failed to update Supabase:", errText);
      return new Response("Internal Error", { status: 500 });
    }

    return new Response("Webhook Processed", { status: 200 });

  } catch (err) {
    console.error("Webhook Error:", err.message);
    return new Response(err.message, { status: 500 });
  }
}
