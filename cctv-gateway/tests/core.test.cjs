const assert = require('node:assert/strict');

const {
  createCsmartIframePlayerHtml,
  extractCsmartBearerFromCapture,
  findCsmartChannel,
  getCsmartChannelSnapshotUrl,
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

function testFindsCsmartChannelByNumberIdOrName() {
  const payload = {
    channels: [
      { id: 'channel-1', number: 1, cameraName: '岗亭01' },
      { id: 'channel-6', number: 6, cameraName: '斜坡03' },
    ],
  };

  assert.equal(findCsmartChannel(payload, 6)?.id, 'channel-6');
  assert.equal(findCsmartChannel(payload.channels, 'channel-1')?.number, 1);
  assert.equal(findCsmartChannel(payload, '斜坡03')?.number, 6);
  assert.equal(findCsmartChannel(payload, 'missing'), null);
}

function testGetsStableSnapshotUrlFromChannelAliases() {
  assert.equal(
    getCsmartChannelSnapshotUrl({ screenshot: 'https://example.test/screenshot.jpg' }),
    'https://example.test/screenshot.jpg',
  );
  assert.equal(
    getCsmartChannelSnapshotUrl({ snapshot_url: 'https://example.test/snapshot-url.jpg' }),
    'https://example.test/snapshot-url.jpg',
  );
  assert.equal(
    getCsmartChannelSnapshotUrl({ snapshotUrl: 'https://example.test/snapshot-url-camel.jpg' }),
    'https://example.test/snapshot-url-camel.jpg',
  );
  assert.equal(
    getCsmartChannelSnapshotUrl({ captureUrl: 'https://example.test/capture.jpg' }),
    'https://example.test/capture.jpg',
  );
  assert.equal(getCsmartChannelSnapshotUrl({}), '');
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

function testIframeHtmlUsesMeetingStyleMainStageWithSwitchableThumbnails() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /id="stage"/);
  assert.match(html, /class="meeting-stage/);
  assert.match(html, /class="main-tile/);
  assert.match(html, /id="thumbnailWall"/);
  assert.match(html, /class="thumbnail-wall/);
  assert.match(html, /renderThumbnailWall/);
  assert.match(html, /--thumbnail-count/);
  assert.match(html, /--thumbnail-columns/);
  assert.match(html, /embeddedMode/);
  assert.match(html, /body\.is-embedded header/);
  assert.match(html, /switchMainChannel/);
  assert.match(html, /draggable = true/);
  assert.match(html, /addEventListener\('click'/);
  assert.match(html, /addEventListener\('dragstart'/);
  assert.match(html, /addEventListener\('dragover'/);
  assert.match(html, /addEventListener\('drop'/);
  assert.match(html, /data-channel-number/);

  for (const id of ['layout', 'channel', 'reload', 'refresh', 'status']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.doesNotMatch(html, /id="openWindow"|独立窗口|openIndependentWindow/);
}

function testOverviewUsesSnapshotsByDefaultAndLiveIframesInLiveMode() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /function snapshotSrc/);
  assert.match(html, /function createSnapshotImage/);
  assert.match(html, /className = 'tile-media'/);
  assert.match(html, /mainTile\.appendChild\(createSnapshotImage\(item\)\)/);
  assert.match(html, /if \(liveMode\) \{\s*thumbnail\.appendChild\(createIframe\(item\)\)/s);
  assert.match(html, /else \{\s*thumbnail\.appendChild\(createSnapshotImage\(item\)\)/s);
  assert.match(html, /iframe\.scrolling = 'no'/);
  assert.doesNotMatch(html, /打开实时|独立窗口|openIndependentWindow/);
}

function testOverviewPreservesVideoAspectRatio() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /\.main-tile \{[^}]*aspect-ratio: 5 \/ 3/s);
  assert.match(html, /\.main-tile \{[^}]*height: auto/s);
  assert.match(html, /\.main-tile \{[^}]*justify-self: center/s);
  assert.match(html, /\.main-tile \{[^}]*width: 100%/s);
  assert.match(html, /\.tile-media \{[^}]*object-fit: contain/s);
  assert.match(html, /\.thumbnail-tile \{[^}]*aspect-ratio: 5 \/ 3/s);
}

function testOverviewUsesTwoRowsAroundLargeCenterLayout() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /\.meeting-stage \{[^}]*grid-template-columns: repeat\(5,/s);
  assert.match(html, /\.main-tile \{[^}]*grid-column: 1 \/ 6/s);
  assert.match(html, /\.main-tile \{[^}]*grid-row: 2/s);
  assert.match(html, /\.thumbnail-wall \{[^}]*display: contents/s);
  assert.match(html, /\.thumbnail-tile:nth-child\(1\) \{ grid-column: 1; grid-row: 1; \}/);
  assert.match(html, /\.thumbnail-tile:nth-child\(5\) \{ grid-column: 5; grid-row: 1; \}/);
  assert.match(html, /\.thumbnail-tile:nth-child\(6\) \{ grid-column: 1; grid-row: 3; \}/);
  assert.match(html, /\.thumbnail-tile:nth-child\(10\) \{ grid-column: 5; grid-row: 3; \}/);
  assert.match(html, /const thumbnails = list\.filter\(\(item\) => Number\(item\.number\) !== selectedChannelNumber\)/);
}

function testTwoRowLayoutKeepsCenterCloseToRows() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /\.meeting-stage \{[^}]*grid-template-rows: auto auto auto/s);
  assert.match(html, /\.meeting-stage \{[^}]*height: auto/s);
  assert.match(html, /\.meeting-stage \{[^}]*width: 100%/s);
  assert.match(html, /body \{[^}]*overflow: auto/s);
}

function testEmbeddedModeKeepsAllCamerasInsideOneLargeStage() {
  const html = createCsmartIframePlayerHtml({
    gatewayBaseUrl: 'http://127.0.0.1:3457',
    playerUrl: 'https://custom.c-smart.hk/csmart-player/cctv-video-list/',
  });

  assert.match(html, /body\.is-embedded \{[^}]*overflow: hidden/s);
  assert.match(html, /body\.is-embedded \.meeting-stage \{[^}]*grid-template-columns: repeat\(5,/s);
  assert.match(html, /body\.is-embedded \.meeting-stage \{[^}]*grid-template-rows: minmax\(0, 1fr\) minmax\(0, 5fr\) minmax\(0, 1fr\)/s);
  assert.match(html, /body\.is-embedded \.thumbnail-wall \{ display: contents; \}/);
  assert.match(html, /body\.is-embedded \.thumbnail-tile \{[^}]*height: 100%/s);
  assert.match(html, /body\.is-embedded \.main-tile \{[^}]*height: 100%/s);
  assert.doesNotMatch(html, /if \(embeddedMode\) return list\.slice\(0, 1\)/);
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
  testFindsCsmartChannelByNumberIdOrName,
  testGetsStableSnapshotUrlFromChannelAliases,
  testIframeHtmlUsesCsmartPostMessageContract,
  testIframeHtmlUsesMeetingStyleMainStageWithSwitchableThumbnails,
  testOverviewUsesSnapshotsByDefaultAndLiveIframesInLiveMode,
  testOverviewPreservesVideoAspectRatio,
  testOverviewUsesTwoRowsAroundLargeCenterLayout,
  testTwoRowLayoutKeepsCenterCloseToRows,
  testEmbeddedModeKeepsAllCamerasInsideOneLargeStage,
  testMasksKnownTokenShapes,
]) {
  test();
}

console.log('cctv-gateway core tests passed');
