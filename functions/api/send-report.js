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
      const { user_email, language, test_mode } = await request.json();
      const RESEND_API_KEY = env.RESEND_API_KEY;

      if (!RESEND_API_KEY) throw new Error("서버에 RESEND_API_KEY 설정이 누락되었습니다.");
      if (!user_email) throw new Error("이메일 주소가 없습니다.");

      let subject, htmlContent;

      // [테스트 모드 로직]
      if (test_mode) {
        subject = language === 'ko' ? "테스트 메일입니다" : "Test Email";
        htmlContent = language === 'ko' 
          ? "<h1>안녕</h1><p>이것은 리센드(Resend)를 통한 한국어 테스트 메일입니다.</p>" 
          : "<h1>Hello</h1><p>This is a test email via Resend in English.</p>";
      } else {
        // [실제 리포트 발송 로직 - 나중에 데이터를 채울 공간]
        subject = language === 'ko' ? "[anse.ai] 금융시장 심리 리포트" : "[anse.ai] Market Sentiment Report";
        htmlContent = `<h1>Report Data goes here</h1>`;
      }

      // Resend API 호출
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
      if (!resendRes.ok) throw new Error(result.message || "Resend 발송 실패");

      return new Response(JSON.stringify({ success: true, id: result.id }), { status: 200, headers: corsHeaders });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: corsHeaders });
}