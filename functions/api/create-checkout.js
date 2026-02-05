export async function onRequestGet(context) {
  const { env } = context;
  const health = {
    endpoint: "create-checkout",
    env_status: {
      POLAR_ACCESS_TOKEN: env.POLAR_ACCESS_TOKEN ? "Set" : "Missing",
      NEXT_PUBLIC_SUPABASE_URL: env.NEXT_PUBLIC_SUPABASE_URL ? "Set" : "Missing",
    }
  };
  return new Response(JSON.stringify(health, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

export async function onRequestPost(context) {
  const { env, request } = context;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
  };

  try {
    // 1. 환경 변수 체크
    const missingVars = [];
    if (!env.POLAR_ACCESS_TOKEN) missingVars.push("POLAR_ACCESS_TOKEN");
    if (!env.NEXT_PUBLIC_SUPABASE_URL) missingVars.push("NEXT_PUBLIC_SUPABASE_URL");

    if (missingVars.length > 0) {
      const errorMsg = `Configuration Error: Missing ${missingVars.join(", ")}`;
      console.error(errorMsg);
      return new Response(JSON.stringify({ error: errorMsg }), { status: 500, headers: corsHeaders });
    }

    const { user_id, user_email } = await request.json();
    const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";

    // 2. Price ID 조회
    const productResponse = await fetch(`https://api.polar.sh/v1/products/${PRODUCT_ID}`, {
      headers: { 'Authorization': `Bearer ${env.POLAR_ACCESS_TOKEN}` },
    });
    
    if (!productResponse.ok) {
      const errData = await productResponse.json();
      throw new Error(`Polar Product Fetch Error: ${errData.detail || productResponse.statusText}`);
    }

    const productData = await productResponse.json();
    const actualPriceId = productData.prices?.[0]?.id;

    if (!actualPriceId) throw new Error("No valid price ID found for this product ID.");

    // 3. Checkout 생성
    const polarResponse = await fetch(`https://api.polar.sh/v1/checkouts/custom/`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.POLAR_ACCESS_TOKEN}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        product_price_id: actualPriceId,
        customer_email: user_email,
        success_url: `${new URL(request.url).origin}/index.html?subscription=success`,
        cancel_url: `${new URL(request.url).origin}/index.html?subscription=cancel`,
        metadata: { supabase_user_id: user_id }
      })
    });

    const result = await polarResponse.json();
    if (!polarResponse.ok) throw new Error(`Polar Checkout Error: ${result.detail || polarResponse.statusText}`);

    return new Response(JSON.stringify({ url: result.url }), { headers: corsHeaders });

  } catch (err) {
    console.error("API Error Log:", err.message);
    return new Response(JSON.stringify({ error: err.message }), { 
      status: 500, 
      headers: corsHeaders 
    });
  }
}