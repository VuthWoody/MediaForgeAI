"""Playwright-based mobile stream sniffer running in an isolated subprocess."""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from typing import Any

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, NetworkError

logger = logging.getLogger(__name__)

MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)


def _detect_platform(url: str) -> str:
    """Identify platform from target URL."""
    low = url.lower()
    if "douyin" in low or "iesdouyin" in low:
        return "Douyin"
    if "tiktok" in low:
        return "TikTok"
    if "youtube" in low or "youtu.be" in low:
        return "YouTube"
    if "bilibili" in low or "b23.tv" in low:
        return "Bilibili"
    if "hongguo" in low or "fanqie" in low:
        return "Hongguo"
    return "Generic"


def run_sniffer_worker(url: str, timeout_sec: int = 30) -> dict[str, Any]:
    """Execute stream sniffing inside the isolated subprocess using Playwright."""
    from playwright.sync_api import sync_playwright

    captured_urls: list[str] = []
    page_title = "Untitled Video"
    platform = _detect_platform(url)

    def on_request(request: Any) -> None:
        req_url = request.url
        # Catch common streaming patterns
        if any(ext in req_url.lower() for ext in (".m3u8", ".mp4", "douyinvod.com", "tiktokcdn", "video_id")):
            if not any(ign in req_url.lower() for ign in (".js", ".css", ".png", ".jpg", ".webp", "log", "stat")):
                captured_urls.append(req_url)

    def on_response(response: Any) -> None:
        try:
            content_type = response.headers.get("content-type", "").lower()
            if "video/" in content_type or "application/vnd.apple.mpegurl" in content_type or "application/x-mpegurl" in content_type:
                captured_urls.append(response.url)
        except Exception:
            pass

    try:
        with sync_playwright() as p:
            # Try native Windows Edge, then Chrome, then default chromium
            browser = None
            for channel in ("msedge", "chrome", None):
                try:
                    launch_kwargs: dict[str, Any] = {"headless": True}
                    if channel:
                        launch_kwargs["channel"] = channel
                    browser = p.chromium.launch(**launch_kwargs)
                    break
                except Exception:
                    continue

            if browser is None:
                return {
                    "status": "error",
                    "error": "Failed to launch any headless browser (Edge/Chrome/Chromium)",
                    "stream_url": None,
                }

            context = browser.new_context(
                user_agent=MOBILE_USER_AGENT,
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
            )
            page = context.new_page()
            page.on("request", on_request)
            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            except Exception:
                pass  # Often network requests keep firing even if navigation times out

            # Wait briefly for dynamic JavaScript stream requests
            start_wait = time.time()
            while time.time() - start_wait < 5.0:
                if captured_urls:
                    break
                time.sleep(0.5)

            try:
                page_title = page.title() or page_title
            except Exception:
                pass

            # Also check DOM for <video src="...">
            try:
                video_srcs = page.eval_on_selector_all("video", "nodes => nodes.map(n => n.src)")
                for src in video_srcs:
                    if src and src.startswith("http"):
                        captured_urls.append(src)
            except Exception:
                pass

            browser.close()

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "stream_url": None,
            "platform": platform,
        }

    # Deduplicate and pick the best candidate
    best_stream: str | None = None
    if captured_urls:
        # Prefer direct .mp4 or .m3u8
        for u in captured_urls:
            if ".mp4" in u or ".m3u8" in u:
                best_stream = u
                break
        if not best_stream:
            best_stream = captured_urls[0]

    if best_stream:
        return {
            "status": "success",
            "stream_url": best_stream,
            "title": page_title.strip(),
            "platform": platform,
            "error": None,
        }
    else:
        return {
            "status": "error",
            "error": f"No media stream detected on page within {timeout_sec}s",
            "stream_url": None,
            "platform": platform,
        }


class PlaywrightScraper:
    """Manages stream sniffing by launching the scraper in a separate isolated subprocess."""

    @classmethod
    def sniff_stream(
        cls,
        url: str,
        timeout_sec: int = 30,
        token: CancellationToken | None = None,
    ) -> dict[str, Any]:
        """Launch the worker in a separate subprocess and return sniffed stream info."""
        if token is not None:
            token.throw_if_cancelled()

        cmd = [
            sys.executable,
            "-m",
            "modules.downloader.scraper",
            "--url",
            url,
            "--timeout",
            str(timeout_sec),
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            raise NetworkError(f"Failed to start stream sniffer subprocess: {e}") from e

        start_time = time.monotonic()
        while proc.poll() is None:
            if token is not None:
                if token.is_cancelled:
                    proc.kill()
                    raise CancelledError("Stream sniffer was cancelled.")
            elapsed = time.monotonic() - start_time
            if elapsed > (timeout_sec + 5):
                proc.kill()
                raise NetworkError(f"Stream sniffer timed out after {timeout_sec}s.")
            time.sleep(0.1)

        stdout, stderr = proc.communicate()
        try:
            # Find the JSON output block from the worker
            json_match = re.search(r"(\{.*\})", stdout, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            elif stdout.strip():
                return json.loads(stdout.strip())
        except Exception:
            pass

        if proc.returncode != 0:
            logger.error("Sniffer subprocess error: %s", stderr)
            raise NetworkError(f"Sniffer subprocess exited with code {proc.returncode}: {stderr.strip()}")

        raise NetworkError(f"Failed to parse sniffer output: {stdout[:200]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediaForge Stream Sniffer Subprocess")
    parser.add_argument("--url", required=True, help="Target page URL")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    args = parser.parse_args()

    res = run_sniffer_worker(args.url, timeout_sec=args.timeout)
    print(json.dumps(res))
    sys.exit(0)
