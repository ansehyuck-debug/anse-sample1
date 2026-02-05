export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

export async function onRequestPost(context) {
  const { env, request } = context;
  const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
  const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";

  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
  };

  try {
    const { user_id, user_email } = await request.json();

    if (!user_id) {
      return new Response(JSON.stringify({ error: "User ID is required" }), { status: 400, headers: corsHeaders });
    }

    const response = await fetch("https://api.polar.sh/v1/checkouts/", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({
        product_id: PRODUCT_ID,
        customer_email: user_email,
        success_url: `${new URL(request.url).origin}/index.html?subscription=success`,
        metadata: {
          supabase_user_id: user_id
        }
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return new Response(JSON.stringify({ error: data.detail || "Failed to create checkout session" }), { 
        status: response.status, 
        headers: corsHeaders 
      });
    }

    return new Response(JSON.stringify({ url: data.url }), { headers: corsHeaders });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
  }
}