export async function onRequest(context) {
  const { request, env } = context;
  const origin = new URL(request.url).origin;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  // 1. OPTIONS (CORS preflight)
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // 2. GET (Health Check)
  if (request.method === "GET") {
    return new Response(JSON.stringify({
      status: "online",
      env_check: {
        POLAR_TOKEN: env.POLAR_ACCESS_TOKEN ? "OK" : "MISSING",
      },
      message: "Please use POST to create a checkout session."
    }, null, 2), { headers: corsHeaders });
  }

  // 3. POST (Create Checkout)
  if (request.method === "POST") {
    try {
      const body = await request.json();
      const { user_id, user_email } = body;

      if (!user_email) throw new Error("user_email is required");

      const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
      if (!POLAR_ACCESS_TOKEN) throw new Error("POLAR_ACCESS_TOKEN missing in environment variables");

      const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";

      // Grok 추천 방식: /v1/checkouts/ 엔드포인트에 products 배열 사용
      const polarRes = await fetch("https://api.polar.sh/v1/checkouts/", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          products: [PRODUCT_ID], 
          customer_email: user_email,
          success_url: `${origin}/index.html?subscription=success`,
          cancel_url: `${origin}/index.html?subscription=cancel`,
          metadata: { 
            supabase_user_id: user_id 
          },
        }),
      });

      const result = await polarRes.json();

      if (!polarRes.ok) {
        console.error("Polar API Error Details:", result);
        throw new Error(result.detail || `Polar error: ${polarRes.status}`);
      }

      return new Response(JSON.stringify({ url: result.url }), {
        status: 200,
        headers: corsHeaders,
      });

    } catch (err) {
      console.error("Checkout Function Error:", err);
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: corsHeaders,
      });
    }
  }

  // 4. Method Not Allowed
  return new Response(JSON.stringify({ error: `Method ${request.method} not allowed` }), {
    status: 405,
    headers: corsHeaders,
  });
}