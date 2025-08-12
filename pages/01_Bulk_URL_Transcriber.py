import streamlit as st
import os
import re
from datetime import datetime
from scraper_service import get_transcript_by_url
import csv
from io import StringIO


st.set_page_config(layout="wide")
st.title("任意URLの一括文字起こし (YouTube / TikTok / Instagram)")

# 保存先（ローカル実行時の参考。CloudではDLボタン利用が基本）
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'transcripts')
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

st.caption("各行に1つのURLを貼り付けてください。対応: YouTube, TikTok, Instagram")
bulk_urls_text = st.text_area(
    "URLリスト",
    height=180,
    placeholder=(
        "https://www.youtube.com/watch?v=...\n"
        "https://www.tiktok.com/@user/video/...\n"
        "https://www.instagram.com/reel/..."
    ),
)

default_filename = datetime.now().strftime("bulk_transcripts_%Y%m%d_%H%M%S.txt")
custom_bulk_filename = st.text_input("保存ファイル名（ダウンロード名）", value=default_filename)

with st.expander("オプション設定", expanded=False):
    col_opt1, col_opt2, col_opt3 = st.columns([1,1,1])
    with col_opt1:
        hl = st.selectbox("言語(hl)", ["ja", "en"], index=0)
    with col_opt2:
        gl = st.selectbox("地域(gl)", ["JP", "US"], index=0)
    with col_opt3:
        max_retries = st.slider("最大リトライ回数", min_value=0, max_value=5, value=2)
    retry_wait_sec = st.slider("リトライ間隔(秒)", min_value=0.0, max_value=10.0, value=1.5, step=0.5)

if st.button("一括文字起こしを実行"):
    urls = [u.strip() for u in bulk_urls_text.splitlines() if u.strip()]
    if not urls:
        st.warning("URLを1つ以上入力してね。")
    else:
        progress = st.progress(0)
        status = st.empty()
        results = []
        csv_rows = []  # URL, platform(not detected here), status, length

        for idx, url in enumerate(urls):
            status.text(f"({idx+1}/{len(urls)}) 取得中: {url[:80]}")
            try:
                data = get_transcript_by_url(url, hl=hl, gl=gl, max_retries=max_retries, retry_wait_sec=retry_wait_sec)
                transcript_text = None
                if isinstance(data, dict) and "transcript" in data:
                    raw = data.get("transcript")
                    if isinstance(raw, list):
                        lines = []
                        for item in raw:
                            if isinstance(item, dict) and 'text' in item:
                                lines.append(item['text'])
                            elif isinstance(item, str):
                                lines.append(item)
                        transcript_text = "\n".join(lines)
                    elif isinstance(raw, str):
                        transcript_text = raw

                if transcript_text:
                    header = (
                        f"URL: {url}\n"
                        f"Downloaded At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"--- START TRANSCRIPT ---\n\n"
                    )
                    results.append(header + transcript_text + "\n\n")
                    csv_rows.append([url, "", "OK", len(transcript_text)])
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
            # クラウド前提でダウンロードボタンのみ表示
            st.download_button(
                label="まとめてダウンロード",
                data=combined_text,
                file_name=re.sub(r'[\\/*?:"<>|]', "", custom_bulk_filename),
                mime="text/plain",
            )

            # CSVダウンロード（サマリー）
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["url", "platform", "status", "length"])
            writer.writerows(csv_rows)
            st.download_button(
                label="サマリーCSVをダウンロード",
                data=csv_buffer.getvalue(),
                file_name=re.sub(r'[\\/*?:"<>|]', "", custom_bulk_filename.replace('.txt', '_summary.csv')),
                mime="text/csv",
            )

            with st.expander("デバッグ：処理ログと先頭プレビュー"):
                st.text("\n".join([r[:200] for r in results[:3]]))
        else:
            status.error("文字起こし結果が空だよ。")


