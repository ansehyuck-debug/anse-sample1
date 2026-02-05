export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400",
    },
  });
}

export async function onRequestPost(context) {
  const { env, request } = context;
  const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
  const PRODUCT_ID = "0d7cce5c-90e9-486a-9137-4c2d359130a5";
  const POLAR_API_BASE_URL = "https://api.polar.sh/v1";

  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
  };

  try {
    const body = await request.json();
    const { user_id, user_email } = body;

    if (!user_id || !user_email) {
      return new Response(JSON.stringify({ error: "User ID and Email are required" }), { 
        status: 400, 
        headers: corsHeaders 
      });
    }

    if (!POLAR_ACCESS_TOKEN) {
      return new Response(JSON.stringify({ error: "Server configuration error: Token missing" }), { 
        status: 500, 
        headers: corsHeaders 
      });
    }

    // 1. 제품 정보 조회하여 Price ID 추출
    const productResponse = await fetch(`${POLAR_API_BASE_URL}/products/${PRODUCT_ID}`, {
      headers: { 'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}` },
    });
    
    if (!productResponse.ok) {
      return new Response(JSON.stringify({ error: "Failed to fetch product details from Polar" }), { 
        status: productResponse.status, 
        headers: corsHeaders 
      });
    }

    const productData = await productResponse.json();
    const actualPriceId = productData.prices?.[0]?.id;

    if (!actualPriceId) {
      return new Response(JSON.stringify({ error: "No valid price ID found for this product" }), { 
        status: 400, 
        headers: corsHeaders 
      });
    }

    // 2. Custom Checkout 생성
    const polarResponse = await fetch(`${POLAR_API_BASE_URL}/checkouts/custom/`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        product_price_id: actualPriceId,
        customer_email: user_email,
        success_url: `${new URL(request.url).origin}/index.html?subscription=success`,
        cancel_url: `${new URL(request.url).origin}/index.html?subscription=cancel`,
        metadata: {
          supabase_user_id: user_id
        }
      })
    });

    const result = await polarResponse.json();

    if (!polarResponse.ok) {
      return new Response(JSON.stringify({ error: result.detail || "Polar API failure" }), { 
        status: polarResponse.status, 
        headers: corsHeaders 
      });
    }

    // 프론트엔드 호환성을 위해 url 키로 반환
    return new Response(JSON.stringify({ url: result.url }), { 
      status: 200, 
      headers: corsHeaders 
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { 
      status: 500, 
      headers: corsHeaders 
    });
  }
}