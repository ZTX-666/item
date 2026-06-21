const fs = require('fs');

async function main() {
  const data = JSON.parse(fs.readFileSync('v16c-stream-data/stream-capture-result.json', 'utf8'));
  const entries = [...(data.playwireCaptured || []), ...(data.jsIntercepted || [])];
  let accessToken = null;
  for (const entry of entries) {
    const body = entry.bodyPreview || entry.body || '';
    if (!String(body).includes('access_token')) continue;
    try {
      const parsed = JSON.parse(body);
      accessToken = parsed && parsed.data && parsed.data.access_token;
    } catch (_) {
      const match = String(body).match(/access_token["\\:]+([0-9a-f-]{36})/i);
      accessToken = match && match[1];
    }
    if (accessToken) break;
  }
  if (!accessToken) throw new Error('C-SMART access token not found in capture');

  const url = 'https://gateway4.c-smart.hk/video/v5/channel/video/listPage?orgId=1778119371126&status=1&hidden=false&relatedIpc=true&pageNum=1&pageSize=11';
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
  const body = await res.text();
  console.log('status', res.status, 'bytes', body.length);
  console.log(body.slice(0, 1200).replace(/at\.[A-Za-z0-9._-]+/g, 'at.<masked>'));

  if (!res.ok) process.exitCode = 1;
  else fs.writeFileSync('csmart-channel-list-latest.json', body);
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
