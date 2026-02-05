export async function onRequest(context) {
  const { request, env } = context;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });

  if (request.method === "POST") {
    try {
      const { user_email, language, market_data, test_mode } = await request.json();
      const RESEND_API_KEY = env.RESEND_API_KEY;

      if (!RESEND_API_KEY) throw new Error("RESEND_API_KEY is missing.");
      
      let subject, htmlContent;

      if (test_mode) {
        subject = language === 'ko' ? "테스트 메일입니다" : "Test Email";
        htmlContent = `<h1>${language === 'ko' ? '안녕' : 'Hello'}</h1>`;
      } else {
        // [Real Report Mode]
        subject = language === 'ko' 
          ? `[anse.ai] KOSPI 금융시장 심리 리포트 (${market_data.score}점)` 
          : `[anse.ai] KOSPI Market Sentiment Report (${market_data.score} pts)`;

        // Prepare Indicator List HTML
        const indicatorsHtml = market_data.indicators.map(ind => `
          <div style="margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">
            <span style="font-weight: bold; color: #333;">${ind.name}:</span>
            <span style="float: right; color: #3d84f5;">${ind.value}</span>
          </div>
        `).join('');

        htmlContent = `
          <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e7ecf4; border-radius: 16px; overflow: hidden; background-color: #ffffff;">
            <!-- Header -->
            <div style="background-color: #3d84f5; padding: 30px; text-align: center; color: white;">
              <h1 style="margin: 0; font-size: 24px;">KOSPI Fear & Greed</h1>
              <p style="margin: 10px 0 0; opacity: 0.9;">Market Sentiment Analysis</p>
            </div>
            
            <!-- Main Score -->
            <div style="padding: 40px 30px; text-align: center;">
              <div style="font-size: 60px; font-weight: 900; color: #3d84f5; margin-bottom: 10px;">${market_data.score}</div>
              <div style="font-size: 20px; font-weight: bold; color: #3d84f5; text-transform: uppercase; letter-spacing: 2px;">${market_data.status}</div>
            </div>

            <!-- Proverb -->
            <div style="padding: 20px 30px; background-color: #f8fafc; border-top: 1px solid #e7ecf4; border-bottom: 1px solid #e7ecf4; font-style: italic; color: #475569; text-align: center;">
              "${market_data.proverb}"
            </div>

            <!-- Market Indicators -->
            <div style="padding: 30px;">
              <h3 style="margin-top: 0; color: #1e293b; border-left: 4px solid #3d84f5; padding-left: 10px;">Market Indicators</h3>
              <div style="margin-top: 20px;">${indicatorsHtml}</div>
            </div>

            <!-- KOSPI Value -->
            <div style="padding: 20px 30px; background-color: #3d84f5; color: white; border-radius: 12px; margin: 0 30px 30px;">
              <div style="font-size: 14px; opacity: 0.8;">KOSPI INDEX</div>
              <div style="font-size: 28px; font-weight: 900;">${market_data.kospi.value}</div>
              <div style="margin-top: 5px;">
                <span style="background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px; font-weight: bold;">${market_data.kospi.change_rate}</span>
                <span style="margin-left: 5px; opacity: 0.9;">${market_data.kospi.change_point}</span>
              </div>
            </div>

            <!-- AI Advice -->
            <div style="padding: 0 30px 40px;">
              <h3 style="color: #1e293b; border-left: 4px solid #3d84f5; padding-left: 10px;">AI Advisor Insights</h3>
              <div style="margin-top: 15px; font-size: 14px; line-height: 1.6; color: #334155;">
                ${market_data.advice}
              </div>
            </div>

            <!-- Footer -->
            <div style="background-color: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b;">
              <p>© 2026 anse.ai. All rights reserved.</p>
              <p>본 리포트는 투자 참고용이며, 최종 투자 책임은 본인에게 있습니다.</p>
            </div>
          </div>
        `;
      }

      // Resend API Send
      const resendRes = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${RESEND_API_KEY}`,
        },
        body: JSON.stringify({
          from: 'anse.ai <info@anse.ai.kr>',
          to: [user_email],
          subject: subject,
          html: htmlContent,
        }),
      });

      const result = await resendRes.json();
      if (!resendRes.ok) throw new Error(result.message || "Resend API error");

      return new Response(JSON.stringify({ success: true, id: result.id }), { status: 200, headers: corsHeaders });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: corsHeaders });
}