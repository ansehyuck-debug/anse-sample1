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
        SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "OK" : "MISSING",
      },
      note: "If POLAR_TOKEN is MISSING, please add POLAR_ACCESS_TOKEN to Cloudflare Pages Settings -> Functions -> Environment variables and REDEPLOY."
    }, null, 2), { headers: corsHeaders });
  }

  // 3. POST (Create Checkout)
  if (request.method === "POST") {
    try {
      const body = await request.json();
      const { user_id, user_email } = body; // Matching frontend keys

      if (!user_email) throw new Error("user_email is required");

      const POLAR_ACCESS_TOKEN = "polar_oat_XiviE9M2x1SnlJ69rhCec6c1qz6CDzteMXBvc4HNXKL";
      if (!POLAR_ACCESS_TOKEN) throw new Error("POLAR_ACCESS_TOKEN missing in environment variables. Check Cloudflare dashboard.");

      const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";
      const POLAR_API_BASE_URL = 'https://api.polar.sh/v1';

      // 1. 제품 정보 조회하여 Price ID 추출 (Reference pattern)
      const productResponse = await fetch(`${POLAR_API_BASE_URL}/products/${PRODUCT_ID}`, {
        headers: { 'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}` },
      });
      
      if (!productResponse.ok) {
        const errorData = await productResponse.json();
        throw new Error(`Polar Product Fetch Error: ${errorData.detail || productResponse.statusText}`);
      }

      const productData = await productResponse.json();
      const actualPriceId = productData.prices?.[0]?.id;

      if (!actualPriceId) {
        throw new Error("유효한 가격 ID를 찾을 수 없습니다.");
      }

      // 2. Custom Checkout 생성 (Reference pattern)
      const polarResponse = await fetch(`${POLAR_API_BASE_URL}/checkouts/custom/`, {
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
          metadata: {
              supabase_user_id: user_id
          }
        }),
      });

      const result = await polarResponse.json();

      if (!polarResponse.ok) {
        throw new Error(result.detail || `Polar Checkout Error: ${polarResponse.status}`);
      }

      // result.url contains the checkout page link
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

  return new Response(JSON.stringify({ error: `Method ${request.method} not allowed` }), {
    status: 405,
    headers: corsHeaders,
  });
}
