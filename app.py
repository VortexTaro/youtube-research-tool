import streamlit as st
import os
import re
import csv
from io import StringIO
from datetime import datetime
from scraper_service import (
    search_youtube,
    get_channel_details,
    get_transcript,
    get_transcript_by_url,
    extract_transcript_text,
)

# --- 定数 ---
SEARCH_LIMIT = 20
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'transcripts')
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# --- Streamlit App ---

st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="YouTube Research Tool")
st.title("YouTube Research Tool")
st.caption("左上の三本線でサイドバーを開けるよ。下に一括文字起こしフォームを埋め込んだよ。")

st.write("---")
st.subheader("任意URLの一括文字起こし (YouTube / TikTok / Instagram)")
bulk_urls_text = st.text_area(
    "URLリスト (各行1つ)",
    height=140,
    placeholder=(
        "https://www.youtube.com/watch?v=...\n"
        "https://www.tiktok.com/@user/video/...\n"
        "https://www.instagram.com/reel/..."
    ),
)
col_opt1, col_opt2, col_opt3 = st.columns([1, 1, 2])
with col_opt1:
    opt_hl = st.selectbox("言語(hl)", ["ja", "en"], index=0)
with col_opt2:
    opt_gl = st.selectbox("地域(gl)", ["JP", "US"], index=0)
with col_opt3:
    opt_retries = st.slider("最大リトライ回数", min_value=0, max_value=5, value=2)
opt_retry_wait = st.slider("リトライ間隔(秒)", min_value=0.0, max_value=10.0, value=1.5, step=0.5)
default_filename = datetime.now().strftime("bulk_transcripts_%Y%m%d_%H%M%S.txt")
bulk_out_name = st.text_input("保存ファイル名（ダウンロード名）", value=default_filename)
if st.button("一括文字起こしを実行"):
    urls = [u.strip() for u in bulk_urls_text.splitlines() if u.strip()]
    if not urls:
        st.warning("URLを1つ以上入力してね。")
    else:
        progress = st.progress(0)
        status = st.empty()
        results = []
        csv_rows = []
        for idx, url in enumerate(urls):
            status.text(f"({idx+1}/{len(urls)}) 取得中: {url[:80]}")
            try:
                data = get_transcript_by_url(
                    url, hl=opt_hl, gl=opt_gl, max_retries=opt_retries, retry_wait_sec=opt_retry_wait
                )
                text = extract_transcript_text(data) if isinstance(data, dict) else None
                if text:
                    header = (
                        f"URL: {url}\n"
                        f"Downloaded At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"--- START TRANSCRIPT ---\n\n"
                    )
                    results.append(header + text + "\n\n")
                    csv_rows.append([url, "", "OK", len(text)])
                else:
                    results.append(f"URL: {url}\nERROR: Transcript not found or invalid response.\n\n")
                    csv_rows.append([url, "", "ERROR", 0])
            except Exception as e:
                results.append(f"URL: {url}\nERROR: {e}\n\n")
                csv_rows.append([url, "", "ERROR", 0])
                with st.expander("デバッグ：例外詳細", expanded=True):
                    st.write(url)
                    st.exception(e)
            progress.progress((idx+1)/len(urls))

        if results:
            combined_text = "".join(results)
            st.download_button(
                label="まとめてダウンロード",
                data=combined_text,
                file_name=re.sub(r'[\\/*?:"<>|]', "", bulk_out_name),
                mime="text/plain",
            )
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["url", "platform", "status", "length"])
            writer.writerows(csv_rows)
            st.download_button(
                label="サマリーCSVをダウンロード",
                data=csv_buffer.getvalue(),
                file_name=re.sub(r'[\\/*?:"<>|]', "", bulk_out_name.replace('.txt', '_summary.csv')),
                mime="text/csv",
            )
            with st.expander("デバッグ：処理ログと先頭プレビュー"):
                st.text("\n".join([r[:200] for r in results[:3]]))
        else:
            status.error("文字起こし結果が空だよ。")

# 検索セクションはページ最下部へ
st.write("---")
st.subheader("YouTubeキーワード検索（オプション設定は上の一括フォームを参照）")

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
                # 1. 動画を検索（言語・地域・リトライを反映）
                opt_hl = st.session_state.get("opt_hl", "ja")
                opt_gl = st.session_state.get("opt_gl", "JP")
                opt_retries = st.session_state.get("opt_retries", 2)
                opt_retry_wait = st.session_state.get("opt_retry_wait", 1.5)
                search_results = search_youtube(
                    search_keyword,
                    limit=SEARCH_LIMIT,
                    hl=opt_hl,
                    gl=opt_gl,
                    max_retries=opt_retries,
                    retry_wait_sec=opt_retry_wait,
                )

                # 2. APIレスポンスを処理
                if isinstance(search_results, str):  # APIがエラー文字列を返した場合
                    st.session_state.error = search_results
                    st.session_state.videos = []
                    with st.expander("デバッグ：検索エラー詳細", expanded=True):
                        st.code(search_results)

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
                    with st.expander("デバッグ：検索レスポンス(不明形式)", expanded=False):
                        st.write(type(search_results).__name__)
                        st.json(search_results)

            except Exception as e:
                st.session_state.error = f"An unexpected error occurred: {e}"
                st.session_state.videos = []
                with st.expander("デバッグ：検索例外詳細", expanded=True):
                    st.exception(e)
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
                        # 言語オプション（簡易）。必要ならUIに昇格可能
                        transcript_data = None
                        try:
                            opt_hl = st.session_state.get("opt_hl", "ja")
                            opt_gl = st.session_state.get("opt_gl", "JP")
                            opt_retries = st.session_state.get("opt_retries", 2)
                            opt_retry_wait = st.session_state.get("opt_retry_wait", 1.5)
                            transcript_data = get_transcript(
                                url,
                                hl=opt_hl,
                                gl=opt_gl,
                                max_retries=opt_retries,
                                retry_wait_sec=opt_retry_wait,
                            )
                        except Exception as e:
                            with st.expander("デバッグ：ダウンロード例外詳細", expanded=True):
                                st.exception(e)

                        # transcript抽出（APIの形状差を吸収）
                        transcript_text = extract_transcript_text(transcript_data) if isinstance(transcript_data, dict) else None
                        
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

                            # ダウンロードのみ
                            st.download_button(
                                label="このトランスクリプトをダウンロード",
                                data=full_content,
                                file_name=filename,
                                mime="text/plain",
                                key=f"dl_{i}"
                            )
                        else:
                            st.error("Could not retrieve transcript for this video.")
                            with st.expander("デバッグ：APIレスポンス（Raw）", expanded=True):
                                st.json(transcript_data)

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
            # Bulk download also respects settings
            opt_hl = st.session_state.get("opt_hl", "ja")
            opt_gl = st.session_state.get("opt_gl", "JP")
            opt_retries = st.session_state.get("opt_retries", 2)
            opt_retry_wait = st.session_state.get("opt_retry_wait", 1.5)
            transcript_data = get_transcript(
                url,
                hl=opt_hl,
                gl=opt_gl,
                max_retries=opt_retries,
                retry_wait_sec=opt_retry_wait,
            )
            transcript_text = extract_transcript_text(transcript_data) if isinstance(transcript_data, dict) else None
            
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