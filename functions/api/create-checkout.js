export async function onRequest(context) {
  const { request, env } = context;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  // 1. OPTIONS 요청 처리 (CORS)
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // 2. GET 요청 처리 (상태 진단)
  if (request.method === "GET") {
    const health = {
      status: "online",
      env_check: {
        POLAR_TOKEN: env.POLAR_ACCESS_TOKEN ? "OK" : "MISSING",
        SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "OK" : "MISSING",
      }
    };
    return new Response(JSON.stringify(health, null, 2), { headers: corsHeaders });
  }

  // 3. POST 요청 처리 (실제 결제 로직)
  if (request.method === "POST") {
    try {
      const { user_id, user_email } = await request.json();
      const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
      const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";

      if (!POLAR_ACCESS_TOKEN) throw new Error("POLAR_ACCESS_TOKEN is not set in Cloudflare.");

      // A. Price ID 조회
      const productRes = await fetch(`https://api.polar.sh/v1/products/${PRODUCT_ID}`, {
        headers: { "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}` }
      });
      const productData = await productRes.json();
      const priceId = productData.prices?.[0]?.id;

      if (!priceId) throw new Error("Valid Price ID not found for this product.");

      // B. Checkout 생성
      const polarRes = await fetch(`https://api.polar.sh/v1/checkouts/custom/`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          product_price_id: priceId,
          customer_email: user_email,
          success_url: `${new URL(request.url).origin}/index.html?subscription=success`,
          cancel_url: `${new URL(request.url).origin}/index.html?subscription=cancel`,
          metadata: { supabase_user_id: user_id }
        })
      });

      const result = await polarRes.json();
      if (!polarRes.ok) throw new Error(result.detail || "Polar API Error");

      return new Response(JSON.stringify({ url: result.url }), { headers: corsHeaders });

    } catch (err) {
      console.error("Checkout Error:", err.message);
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
    }
  }

  // 4. 지원하지 않는 메서드
  return new Response(JSON.stringify({ error: `Method ${request.method} not allowed` }), { 
    status: 405, 
    headers: corsHeaders 
  });
}
