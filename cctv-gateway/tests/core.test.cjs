const assert = require('node:assert/strict');

const {
  createCsmartIframePlayerHtml,
  extractCsmartBearerFromCapture,
  maskSecret,
  normalizeCsmartChannelPayload,
} = require('../src/csmart-player-core.cjs');

function testExtractsBearerFromCapture() {
  const token = extractCsmartBearerFromCapture({
    playwireCaptured: [
      { url: 'https://gateway4.c-smart.hk/other', bodyPreview: '{}' },
      {
        url: 'https://gateway4.c-smart.hk/oauth/oauth/token',
        bodyPreview: JSON.stringify({ data: { access_token: '12345678-1234-1234-1234-123456789abc' } }),
      },
    ],
  });

  assert.equal(token, '12345678-1234-1234-1234-123456789abc');
}

function testNormalizesActiveCameraChannels() {
  const normalized = normalizeCsmartChannelPayload(
    {
      code: 200,
      data: {
        totalCount: 3,
        list: [
          { number: 11, cameraName: 'eleven', status: 1, deviceType: 1 },
          { number: 4, cameraName: 'hidden', status: 0, deviceType: 1 },
          { number: 1, cameraName: 'one', status: 1, deviceType: 1 },
          { number: 2, cameraName: 'not ipc', status: 1, deviceType: 2 },
        ],
      },
    },
    'test',
  );

  assert.equal(normalized.ok, true);
  assert.equal(normalized.source, 'test');
  assert.deepEqual(normalized.channels.map((item) => item.number), [1, 11]);
}

function testIframeHtmlUsesCsmartPostMessageContract() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /iframeInit/);
  assert.match(html, /postMessage/);
  assert.match(html, /\/api\/csmart\/channels/);
  assert.match(html, /custom\.c-smart\.hk\/csmart-player\/cctv-video-list/);
  assert.match(html, /通道加载失败/);
}

function testMasksKnownTokenShapes() {
  const masked = maskSecret('Bearer 12345678-1234-1234-1234-123456789abc at.secret dv.secret accessToken=abc');

  assert.equal(masked.includes('12345678-1234-1234-1234-123456789abc'), false);
  assert.equal(masked.includes('at.secret'), false);
  assert.equal(masked.includes('dv.secret'), false);
  assert.match(masked, /Bearer <masked>/);
}

for (const test of [
  testExtractsBearerFromCapture,
  testNormalizesActiveCameraChannels,
  testIframeHtmlUsesCsmartPostMessageContract,
  testMasksKnownTokenShapes,
]) {
  test();
}

console.log('cctv-gateway core tests passed');
