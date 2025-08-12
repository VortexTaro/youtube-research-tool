import os
import re
import requests
from urllib.parse import quote
import time
from dotenv import load_dotenv

try:
    import streamlit as st  # Optional: available on Streamlit Cloud
except Exception:
    st = None

load_dotenv()

def _get_api_key():
    # Priority: Streamlit secrets -> env var
    if st is not None:
        try:
            secret_val = st.secrets.get("SCRAPE_CREATORS_API_KEY")
            if secret_val:
                return secret_val
        except Exception:
            pass
    env_val = os.getenv("SCRAPE_CREATORS_API_KEY")
    if env_val:
        return env_val
    return None

API_KEY = _get_api_key()
BASE_URL = "https://api.scrapecreators.com/v1"

def search_youtube(keyword, limit=10, hl="ja", gl="JP", max_retries=2, retry_wait_sec=1.5):
    """
    Searches YouTube for videos based on a keyword.
    On error, returns the error message string.
    """
    if not API_KEY:
        return "API key for Scrape Creators not found. Please set it in Streamlit Secrets or environment variable."

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    search_url = f"{BASE_URL}/youtube/search?query={keyword}&limit={limit}&hl={hl}&gl={gl}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_wait_sec)
                continue
            error_message = f"API Error: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
            return error_message

def get_channel_details(channel_id):
    """
    Gets details for a given YouTube channel ID.
    On error, returns the error message string.
    """
    if not API_KEY:
        return "API key for Scrape Creators not found. Please set it in Streamlit Secrets or environment variable."

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    channel_url = f"{BASE_URL}/youtube/channel/details?id={channel_id}"

    try:
        response = requests.get(channel_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_message = f"API Error getting channel details for ID {channel_id}: {e}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        return error_message

def _detect_platform_from_url(video_url: str):
    """Return one of 'youtube', 'tiktok', 'instagram', or None based on URL."""
    if not isinstance(video_url, str) or not video_url:
        return None
    url_lower = video_url.lower()
    if any(host in url_lower for host in ["youtube.com", "youtu.be"]):
        return "youtube"
    if "tiktok.com" in url_lower:
        return "tiktok"
    if "instagram.com" in url_lower:
        return "instagram"
    return None


def get_transcript_by_url(video_url: str, hl: str = "ja", gl: str = "JP", max_retries: int = 2, retry_wait_sec: float = 1.5):
    """
    Gets transcript for a given video URL across supported platforms
    (YouTube, TikTok, Instagram) using ScrapeCreators API.

    Returns JSON dict on success, or error string on failure.
    """
    if not API_KEY:
        return "API key for Scrape Creators not found. Please set it in Streamlit Secrets or environment variable."

    platform = _detect_platform_from_url(video_url)
    if platform is None:
        return f"Unsupported URL/platform: {video_url}"

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    # Build endpoint per platform
    encoded_url = quote(video_url, safe="")
    if platform == "youtube":
        endpoint = f"{BASE_URL}/youtube/video/transcript?url={encoded_url}&hl={hl}&gl={gl}"
    elif platform == "tiktok":
        endpoint = f"{BASE_URL}/tiktok/video/transcript?url={encoded_url}"
    else:  # instagram
        endpoint = f"{BASE_URL}/instagram/video/transcript?url={encoded_url}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_wait_sec)
                continue
            error_message = f"API Error getting transcript for URL {video_url}: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
            return error_message


# Backward-compatible alias for existing YouTube flow inside the app
def get_transcript(
    video_url: str,
    hl: str = "ja",
    gl: str = "JP",
    max_retries: int = 2,
    retry_wait_sec: float = 1.5,
):
    return get_transcript_by_url(
        video_url,
        hl=hl,
        gl=gl,
        max_retries=max_retries,
        retry_wait_sec=retry_wait_sec,
    )