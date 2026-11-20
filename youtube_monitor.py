"""Optional public YouTube live-chat watcher for an explicitly labelled DEMO.

Requires a YouTube Data API v3 key in the server's environment. Only actual
superChatEvent/superStickerEvent messages are ingested. Synthetic messages still
use the existing /api/simulate endpoint. Neither client-side JS nor GitHub Pages
receives the API key.

This list()-based demonstration is not a 24/7 production collector. Google
recommends streamList() for lower-latency and reduced polling/quota costs.
"""
from __future__ import annotations

import asyncio
import math
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import store

VIDEO_ENDPOINT = 'https://www.googleapis.com/youtube/v3/videos'
CHAT_ENDPOINT = 'https://www.googleapis.com/youtube/v3/liveChat/messages'
PAID = frozenset(('superChatEvent', 'superStickerEvent'))
VIDEO_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{11}$')


def video_id_from_input(value: str) -> str:
    raw = value.strip()
    if VIDEO_ID_PATTERN.fullmatch(raw):
        return raw
    parsed = urlparse(raw)
    if parsed.scheme != 'https' or (parsed.hostname or '').lower() not in (
        'youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtu.be'):
        raise ValueError('Use a YouTube video ID or an HTTPS youtube.com/youtu.be live URL')
    host = (parsed.hostname or '').lower()
    if host.endswith('youtu.be'):
        video_id = parsed.path.strip('/').split('/')[0]
    elif parsed.path == '/watch':
        video_id = (parse_qs(parsed.query).get('v') or [''])[0]
    elif parsed.path.startswith(('/live/', '/embed/')):
        video_id = parsed.path.split('/')[2]
    else:
        video_id = ''
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError('Could not find an 11-character YouTube video ID')
    return video_id


def normalize_paid_event(message: dict) -> dict | None:
    """Validate a public chat event before passing it to the existing scorer."""
    snippet = message.get('snippet') or {}
    kind = snippet.get('type')
    if kind not in PAID:
        return None
    details = snippet.get('superChatDetails' if kind == 'superChatEvent' else 'superStickerDetails') or {}
    msg_id = message.get('id')
    if not isinstance(msg_id, str) or not (1 <= len(msg_id) <= 150):
        return None
    try:
        micros = int(details.get('amountMicros', 0))
    except (TypeError, ValueError):
        return None
    currency = str(details.get('currency', '')).upper()
    if micros <= 0 or not re.fullmatch('[A-Z]{3}', currency):
        return None
    # Only USD gets automatic points; other currencies enter manual review.
    timestamp = str(snippet.get('publishedAt') or datetime.now(timezone.utc).isoformat())
    donor = str((message.get('authorDetails') or {}).get('displayName') or 'YouTube Viewer')[:100]
    comment = str(details.get('userComment') or '')[:500] if kind == 'superChatEvent' else ''
    safe_details = dict(details, amountMicros=str(micros), currency=currency, userComment=comment,
                        amountDisplayString=str(details.get('amountDisplayString') or '')[:80])
    return {'id': 'yt:' + msg_id, 'snippet': {'type':kind, 'publishedAt':timestamp,
            'superChatDetails' if kind == 'superChatEvent' else 'superStickerDetails': safe_details},
            'authorDetails':{'displayName':donor}}


class YouTubeMonitor:
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY', '').strip()
        self.default_video_id = os.getenv('YOUTUBE_VIDEO_ID', '').strip()
        self.default_enabled = os.getenv('YOUTUBE_ENABLED', '0') == '1'
        try:
            poll_seconds = float(os.getenv('YOUTUBE_MIN_POLL_SECONDS', '50'))
        except ValueError:
            poll_seconds = 50.0
        self.poll_seconds = max(5.0, poll_seconds) if math.isfinite(poll_seconds) else 50.0
        self.connected = False
        self.status = 'disabled'
        self.error = ''
        self.live_chat_id = ''
        self.last_checked = None
        self.last_paid_at = None
        self.seen_paid = 0
        self.imported = 0
        self.duplicates = 0
        self.video_id = ''
        self._page_token = ''
        self._primed = False
        self._wake = None
        self._config_revision = 0

    def config(self):
        return store.youtube_config(self.default_video_id, self.default_enabled)

    def configuration_changed(self):
        self._config_revision += 1
        if self._wake is not None:
            self._wake.set()

    def snapshot(self):
        c = self.config()
        return {'enabled': c['enabled'], 'video_id': c['video_id'],
                'api_key_configured': bool(self.api_key), 'connected':self.connected,
                'status':self.status, 'error':self.error, 'live_chat_found':bool(self.live_chat_id),
                'poll_interval_seconds':self.poll_seconds,
                'last_checked':self.last_checked, 'last_paid_at':self.last_paid_at,
                'paid_messages_seen':self.seen_paid, 'events_recorded':self.imported,
                'duplicates_skipped':self.duplicates,
                'note':'Production isolates tests from live rankings; staging may mix event sources.'}

    def _switch(self, vid):
        self.video_id = vid
        self.live_chat_id = ''
        checkpoint = store.get_youtube_checkpoint(vid) if vid else None
        self._page_token = checkpoint['page_token'] if checkpoint else ''
        self._primed = bool(checkpoint and checkpoint['primed'])
        self.connected = False
        self.error = ''
        self.status = 'connecting' if vid else 'disabled'

    async def _sleep(self, stop: asyncio.Event, seconds: float):
        if stop.is_set():
            return
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=max(0.5, seconds))
        except asyncio.TimeoutError:
            pass
        finally:
            self._wake.clear()

    @staticmethod
    def _check_response(response: httpx.Response) -> dict:
        if response.status_code != 200:
            reason = ''
            try:
                reason = str(response.json().get('error', {}).get('errors', [{}])[0].get('reason', ''))
            except (ValueError, IndexError, AttributeError, TypeError):
                pass
            raise ValueError(f'YouTube API HTTP {response.status_code}' + (f' ({reason[:80]})' if reason else ''))
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Invalid YouTube API response')
        return data

    async def _resolve_chat(self, client: httpx.AsyncClient):
        response = await client.get(VIDEO_ENDPOINT, params={'part':'liveStreamingDetails','id':self.video_id},
                                    headers={'X-Goog-Api-Key': self.api_key})
        doc = self._check_response(response)
        video = (doc.get('items') or [{}])[0]
        live_chat = (video.get('liveStreamingDetails') or {}).get('activeLiveChatId')
        if not live_chat:
            self.status = 'waiting-for-live-chat'
            self.connected = False
            return False
        self.live_chat_id = str(live_chat)
        self.status = 'priming-chat'
        return True

    async def _poll_chat(self, client: httpx.AsyncClient):
        revision = self._config_revision
        params = {'part':'id,snippet,authorDetails','liveChatId':self.live_chat_id,
                  'maxResults':200}
        if self._page_token:
            params['pageToken'] = self._page_token
        response = await client.get(CHAT_ENDPOINT, params=params, headers={'X-Goog-Api-Key': self.api_key})
        if revision != self._config_revision:
            return 0
        doc = self._check_response(response)
        self.last_checked = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.connected = True
        self.status = 'listening'
        self.error = ''
        token = doc.get('nextPageToken')
        # On connecting, establish a baseline rather than replaying pre-existing donations.
        # Start monitoring before asking viewers to make a real Super Chat.
        if self._primed:
            for raw in doc.get('items') or []:
                parsed = normalize_paid_event(raw)
                if parsed is None:
                    continue
                self.seen_paid += 1
                self.last_paid_at = self.last_checked
                try:
                    result = store.ingest(parsed, source='youtube')
                except ValueError:
                    continue
                if result['result'] == 'created':
                    self.imported += 1
                elif result['result'] == 'duplicate':
                    self.duplicates += 1
        if isinstance(token, str):
            store.save_youtube_checkpoint(self.video_id, token, True)
            self._page_token = token
        self._primed = True
        try:
            official_wait = float(doc.get('pollingIntervalMillis') or 0) / 1000
        except (TypeError, ValueError):
            official_wait=0.0
        return max(self.poll_seconds, official_wait)

    async def run(self, stop: asyncio.Event):
        self._wake = asyncio.Event()
        self._switch('')
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            while not stop.is_set():
                try:
                    revision = self._config_revision
                    config = self.config()
                    enabled = bool(config['enabled'])
                    vid = str(config['video_id'])
                    if not enabled or not self.api_key or not vid:
                        if self.video_id or self.live_chat_id:
                            self._switch('')
                        self.status = ('missing-api-key' if enabled and not self.api_key else
                                       'missing-video-id' if enabled and not vid else 'disabled')
                        self.connected = False
                        await self._sleep(stop, 2)
                        continue
                    if vid != self.video_id:
                        self._switch(vid)
                    if not self.live_chat_id:
                        if not await self._resolve_chat(client):
                            await self._sleep(stop, 20)
                            continue
                    if revision != self._config_revision:
                        continue
                    delay = await self._poll_chat(client)
                    await self._sleep(stop, delay)
                except (httpx.HTTPError, ValueError, KeyError, IndexError, AttributeError, TypeError) as exc:
                    self.error = str(exc)[:180] if isinstance(exc, ValueError) else type(exc).__name__
                    self.connected = False
                    self.status = 'error'
                    # A concluded chat ID needs to be resolved again.
                    if any(tag in self.error for tag in ('liveChatEnded','liveChatNotFound','pageTokenInvalid')):
                        self.live_chat_id = ''
                        self._page_token = ''
                        self._primed = False
                        store.clear_youtube_checkpoint(self.video_id)
                    await self._sleep(stop, 25)
