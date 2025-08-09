# YouTube Research Tool

This tool allows you to search for YouTube videos by keyword, retrieve a list of videos, and then get the transcript for a selected video.

Additionally, it now supports bulk transcription from arbitrary URLs for YouTube, TikTok, and Instagram.

## Features

- Search for YouTube videos using a keyword.
- Fetch up to 10 videos based on the search query.
- View video details (title, channel, URL).
- Get the transcript of a selected video.
- Download the transcript as a text file.
- Bulk transcription for arbitrary URLs (YouTube / TikTok / Instagram)

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd youtube-research-tool
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your API key:**
    - Option A (Local dev): Create a `.env` file and add your Scrape Creators API key:
      ```
      SCRAPE_CREATORS_API_KEY="YOUR_API_KEY_HERE"
      ```
    - Option B (Streamlit Cloud): Set the secret in your app settings (`Settings > Secrets`):
      ```
      SCRAPE_CREATORS_API_KEY = "YOUR_API_KEY_HERE"
      ```

## Usage

Run the Streamlit application:

```bash
streamlit run app.py
```

Open your web browser and go to the local URL provided by Streamlit (usually `http://localhost:8501`). 

### Bulk Transcription (YouTube / TikTok / Instagram)

1. Open the expander titled "任意URLの一括文字起こし (YouTube / TikTok / Instagram)".
2. Paste one URL per line. Supported examples:
   - `https://www.youtube.com/watch?v=...`
   - `https://www.tiktok.com/@user/video/...`
   - `https://www.instagram.com/reel/...`
3. Click the execute button. A combined transcript file will be saved under the `transcripts` folder.

## Deploy to Streamlit Cloud

1. Push this folder to a public GitHub repository.
2. On Streamlit Cloud, create a new app and select your repo/branch, main file `youtube_research_tool_new/app.py`.
3. In `App settings > Secrets`, add:
   ```
   SCRAPE_CREATORS_API_KEY = "YOUR_API_KEY_HERE"
   ```
4. Deploy. The app will run without local `.env` because it reads `st.secrets` as fallback.