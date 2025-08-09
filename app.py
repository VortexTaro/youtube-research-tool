import streamlit as st
import os
import re
from datetime import datetime
from scraper_service import search_youtube, get_channel_details, get_transcript, get_transcript_by_url

# --- 定数 ---
SEARCH_LIMIT = 20
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'transcripts')
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# --- Streamlit App ---

st.set_page_config(layout="wide")
st.title("YouTube Research Tool")
st.caption("サイドバーのPagesから『任意URLの一括文字起こし』ページも使えるよ。")

# --- Session Stateの初期化 ---
if "videos" not in st.session_state:
    st.session_state.videos = None
if "error" not in st.session_state:
    st.session_state.error = None
if "last_keyword" not in st.session_state:
    st.session_state.last_keyword = ""

# --- UIコンポーネント ---
search_keyword = st.text_input("Enter search keyword", value=st.session_state.get("last_keyword", ""))

if st.button("Search"):
    if search_keyword:
        # 新しい検索のたびに状態をリセット
        st.session_state.videos = None
        st.session_state.error = None
        st.session_state.last_keyword = search_keyword

        with st.spinner("Searching for videos..."):
            try:
                # 1. 動画を検索
                search_results = search_youtube(search_keyword, limit=SEARCH_LIMIT)

                # --- デバッグ情報 ---
                with st.expander("デバッグ情報：APIからの生データ"):
                    st.json(search_results)
                # --- デバッグ情報終わり ---

                # 2. APIレスポンスを処理
                if isinstance(search_results, str):  # APIがエラー文字列を返した場合
                    st.session_state.error = search_results
                    st.session_state.videos = []

                # 正常に宝箱（辞書型）が返ってきた場合の処理
                elif search_results and isinstance(search_results, dict) and 'videos' in search_results:
                    video_list = search_results.get('videos', [])
                    channel_list = search_results.get('channels', [])

                    # チャンネルIDをキーとして購読者数を持つ辞書（ルックアップテーブル）を作成
                    channel_subscribers = {c.get('id'): c.get('subscriberCountText', 'N/A') for c in channel_list if isinstance(c, dict)}

                    if not video_list:
                        st.session_state.videos = []
                    else:
                        enriched_videos = []
                        for video in video_list:
                            if not isinstance(video, dict):
                                continue

                            # 作成したルックアップテーブルから購読者数を効率的に取得
                            channel_id = video.get('channel', {}).get('id')
                            subscriber_count = channel_subscribers.get(channel_id, 'N/A')
                            video['channel_details'] = {'subscriberCountText': subscriber_count}
                            enriched_videos.append(video)

                        st.session_state.videos = enriched_videos
                        st.success("All video details loaded!")

                else: # 検索結果が空、または予期しない形式だった場合
                    st.session_state.videos = []

            except Exception as e:
                st.session_state.error = f"An unexpected error occurred: {e}"
                st.session_state.videos = []
                st.exception(e) # 詳細なエラーをコンソールと画面に出力
    else:
        st.warning("Please enter a keyword to search.")


# --- 結果表示 ---

# エラーがあれば表示
if st.session_state.get("error"):
    st.error(st.session_state.error)

# 検索結果（動画リスト）があれば表示
if st.session_state.get("videos") is not None:
    videos = st.session_state.videos
    if not videos:
        st.info("No videos found.")
    else:
        st.write(f"Found {len(videos)} videos.")
        for i, video in enumerate(videos):
            st.write("---")
            col1, col2 = st.columns([1, 4])

            with col1:
                thumbnail_url = video.get("thumbnail")
                if thumbnail_url and isinstance(thumbnail_url, str):
                    st.image(thumbnail_url, width=160)
                else:
                    st.image("https://via.placeholder.com/160x90.png?text=No+Thumbnail", width=160)

            with col2:
                title = video.get('title', 'No Title')
                url = video.get('url', '#')
                channel_name = video.get('channel', {}).get('title', 'N/A')
                view_count = video.get('viewCountText', 'N/A')
                published_date = video.get('publishedTimeText', 'N/A')
                # チャンネル詳細から購読者数を取得
                subscriber_count = video.get('channel_details', {}).get('subscriberCountText', 'N/A')

                st.subheader(f"{i + 1}. {title}")
                st.caption(f"**Channel:** {channel_name} | **Subscribers:** {subscriber_count} | **Views:** {view_count} | **Uploaded:** {published_date}")
                st.caption(f"**URL:** {url}")

                if st.button("Download Transcript", key=f"download_{i}"):
                    with st.spinner(f"Downloading transcript for '{title[:30]}...'"):
                        transcript_data = get_transcript(url)

                        # Check if the transcript is a valid string
                        transcript_text = None
                        if isinstance(transcript_data, dict) and "transcript" in transcript_data:
                            raw_transcript = transcript_data.get("transcript")
                            if isinstance(raw_transcript, list):
                                processed_lines = []
                                for item in raw_transcript:
                                    if isinstance(item, dict) and 'text' in item:
                                        processed_lines.append(item['text'])
                                    elif isinstance(item, str):
                                        processed_lines.append(item)
                                transcript_text = "\n".join(processed_lines)
                            elif isinstance(raw_transcript, str):
                                transcript_text = raw_transcript
                        
                        if transcript_text:
                            # ファイル名をサニタイズ
                            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
                            filename = f"{safe_title}_transcript.txt"
                            filepath = os.path.join(TRANSCRIPTS_DIR, filename)

                            # メタデータヘッダーを作成
                            download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            header = (
                                f"Title: {title}\n"
                                f"Channel: {channel_name}\n"
                                f"Subscribers: {subscriber_count}\n"
                                f"Views: {view_count}\n"
                                f"Published: {published_date}\n"
                                f"URL: {url}\n"
                                f"Downloaded At: {download_date}\n"
                                f"--- START TRANSCRIPT ---\n\n"
                            )
                            full_content = header + transcript_text

                            # 先にデバッグ表示（Rawレスポンス・本文プレビュー）
                            with st.expander("デバッグ：APIレスポンス（Raw）"):
                                st.json(transcript_data)
                            with st.expander("プレビュー（保存/ダウンロード前に確認）", expanded=True):
                                st.text_area(label="Transcript", value=transcript_text, height=200)

                            # 保存とダウンロードをユーザー操作に変更
                            col1d, col2d = st.columns([1,1])
                            with col1d:
                                if st.button("保存する", key=f"save_{i}"):
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        f.write(full_content)
                                    st.success(f"Transcript saved to: {filepath}")
                            with col2d:
                                st.download_button(
                                    label="このトランスクリプトをダウンロード",
                                    data=full_content,
                                    file_name=filename,
                                    mime="text/plain",
                                    key=f"dl_{i}"
                                )
                        else:
                            # デバッグ用：エラー時もRawを表示
                            with st.expander("デバッグ：APIレスポンス（Raw）"):
                                st.json(transcript_data)
                            st.error("Could not retrieve transcript for this video. 上のRawレスポンスを確認してね。")

# --- バルクダウンロードセクション ---
if st.session_state.get("videos"):
    st.write("---")
    st.header("Bulk Download")
    if st.button("Download All Transcripts"):
        all_transcripts_content = []
        bulk_progress = st.progress(0)
        bulk_status = st.empty()

        for i, video in enumerate(st.session_state.videos):
            title = video.get('title', 'No Title')
            url = video.get('url', '#')
            bulk_status.text(f"Downloading transcript for '{title[:30]}...' ({i+1}/{len(st.session_state.videos)})")
            transcript_data = get_transcript(url)

            transcript_text = None
            if isinstance(transcript_data, dict) and "transcript" in transcript_data:
                raw_transcript = transcript_data.get("transcript")
                if isinstance(raw_transcript, list):
                    processed_lines = []
                    for item in raw_transcript:
                        if isinstance(item, dict) and 'text' in item:
                            processed_lines.append(item['text'])
                        elif isinstance(item, str):
                            processed_lines.append(item)
                    transcript_text = "\n".join(processed_lines)
                elif isinstance(raw_transcript, str):
                    transcript_text = raw_transcript
            
            if transcript_text:
                channel_name = video.get('channel', {}).get('title', 'N/A')
                view_count = video.get('viewCountText', 'N/A')
                subscriber_count = video.get('channel_details', {}).get('subscriberCountText', 'N/A')
                published_date = video.get('publishedTimeText', 'N/A')
                download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                header = (
                    f"--- Video {i+1} ---\n"
                    f"Title: {title}\n"
                    f"Channel: {channel_name}\n"
                    f"Subscribers: {subscriber_count}\n"
                    f"Views: {view_count}\n"
                    f"Published: {published_date}\n"
                    f"URL: {url}\n"
                    f"Downloaded At: {download_date}\n"
                    f"--- START TRANSCRIPT ---\n\n"
                )
                all_transcripts_content.append(header + transcript_text + "\n\n")
            bulk_progress.progress((i+1)/len(st.session_state.videos))

        if all_transcripts_content:
            combined_content = "".join(all_transcripts_content)
            keyword = st.session_state.last_keyword
            safe_keyword = re.sub(r'[\\/*?:"<>|]', "", keyword)
            filename = f"Bulk_{safe_keyword}_transcripts.txt"
            filepath = os.path.join(TRANSCRIPTS_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(combined_content)

            bulk_status.success(f"All transcripts saved to: {filepath}")
            # ブラウザから直接ダウンロード
            st.download_button(
                label="すべてまとめてダウンロード",
                data=combined_content,
                file_name=filename,
                mime="text/plain"
            )
        else:
            bulk_status.error("No transcripts could be downloaded.") 