export async function onRequest(context) {
  const { request, env } = context;
  const origin = new URL(request.url).origin;
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
        SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "OK" : "MISSING",
      },
      instructions: "If MISSING, add POLAR_ACCESS_TOKEN to Cloudflare Settings -> Functions -> Environment variables and REDEPLOY."
    }, null, 2), { headers: corsHeaders });
  }

  if (request.method === "POST") {
    try {
      const { user_id, user_email } = await request.json();
      const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN; // Back to environment variable
      
      if (!POLAR_ACCESS_TOKEN) throw new Error("POLAR_ACCESS_TOKEN is missing in server environment.");

      const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";
      const POLAR_API_BASE_URL = 'https://api.polar.sh/v1';

      // 1. Get Price ID
      const productRes = await fetch(`${POLAR_API_BASE_URL}/products/${PRODUCT_ID}`, {
        headers: { 'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}` },
      });
      const productData = await productRes.json();
      const actualPriceId = productData.prices?.[0]?.id;

      if (!actualPriceId) throw new Error("Valid price ID not found.");

      // 2. Create Checkout
      const polarRes = await fetch(`${POLAR_API_BASE_URL}/checkouts/custom/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}`,
        },
        body: JSON.stringify({
          product_price_id: actualPriceId,
          customer_email: user_email,
          success_url: `${origin}/index.html?subscription=success`,
          cancel_url: `${origin}/index.html?subscription=cancel`,
          metadata: { supabase_user_id: user_id }
        }),
      });

      const result = await polarRes.json();
      if (!polarRes.ok) throw new Error(result.detail || "Polar Checkout failure");

      return new Response(JSON.stringify({ url: result.url }), { status: 200, headers: corsHeaders });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: corsHeaders });
}