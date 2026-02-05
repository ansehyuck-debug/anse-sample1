export const onRequestPost = async (context: any) => {
  const { request, env } = context;
  
  try {
    const { customerEmail, modelProvider, language = 'ko' } = await request.json();
    
    // 환경변수는 Cloudflare Pages 대시보드에서 설정해야 합니다.
    const POLAR_ACCESS_TOKEN = env.POLAR_ACCESS_TOKEN;
    const PRODUCT_ID = 'eaa40322-345f-4be2-bc9e-334a0e1dae77';
    const POLAR_API_BASE_URL = 'https://api.polar.sh/v1';

    // 1. 제품 정보 조회
    const productResponse = await fetch(`${POLAR_API_BASE_URL}/products/${PRODUCT_ID}`, {
      headers: { 'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}` },
    });
    
    const productData: any = await productResponse.json();
    const actualPriceId = productData.prices?.[0]?.id;

    if (!actualPriceId) {
      return new Response(JSON.stringify({ error: '유효한 가격 ID를 찾을 수 없습니다.' }), { 
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // 2. Checkout 생성
    const polarResponse = await fetch(`${POLAR_API_BASE_URL}/checkouts/custom/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${POLAR_ACCESS_TOKEN}`,
      },
      body: JSON.stringify({
        product_price_id: actualPriceId,
        customer_email: customerEmail,
        success_url: `${new URL(request.url).origin}/success?polar_checkout_session_id={CHECKOUT_SESSION_ID}&model_provider=${modelProvider || 'openai'}&lang=${language}`,
        cancel_url: `${new URL(request.url).origin}/cancel?lang=${language}`,
        metadata: {
            model_provider: modelProvider || 'openai',
            language: language
        }
      }),
    });

    const result: any = await polarResponse.json();
    return new Response(JSON.stringify({ checkout_url: result.url }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error: any) {
    return new Response(JSON.stringify({ error: error.message }), { 
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
