// functions/api/fred.js
export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  
  // series_id를 쿼리 파라미터에서 받음 (기본값 SP500)
  const series = url.searchParams.get('series') || 'SP500';
  
  const params = new URLSearchParams({
    series_id: series,
    api_key: env.FRED_API_KEY,
    file_type: 'json',
    sort_order: 'desc',
    limit: '1' // 최신 데이터 1개만 가져옴
  });

  const fredUrl = `https://api.stlouisfed.org/fred/series/observations?${params}`;

  try {
    const response = await fetch(fredUrl);
    if (!response.ok) {
      throw new Error(`FRED API Error: ${response.status}`);
    }

    const data = await response.json();

    return new Response(JSON.stringify(data), {
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
