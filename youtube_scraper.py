import os
import io
import sys
import csv
import subprocess
import re
from tqdm import tqdm
from time import sleep

from config import API_KEY, SERVICE_ACCOUNT_FILE, CHANNEL_URL, BUCKET_NAME
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

# Create the output folders if they don't exist
os.makedirs('webm_files', exist_ok=True)
os.makedirs('wav_files', exist_ok=True)

def build_youtube_service(api_key):
    return build("youtube", "v3", developerKey=api_key)

def build_speech_client(service_account_file):
    credentials = service_account.Credentials.from_service_account_file(service_account_file)
    return speech.SpeechClient(credentials=credentials)

def get_all_videos(youtube, channel_id):
    videos = []

    # Retrieve video metadata
    request = youtube.search().list(
        channelId=channel_id,
        type='video',
        part='id,snippet',
        maxResults=50,
        fields='items(id(videoId),snippet(title,description,publishedAt))'
    )

    while request:
        response = request.execute()
        videos.extend(response['items'])
        request = youtube.search().list_next(request, response)

    return videos

def transcribe_video(youtube, speech_client, video_id):
    # Download the audio file
    video_info = youtube.videos().list(part='snippet', id=video_id).execute()
    title = video_info['items'][0]['snippet']['title']
    audio_file_mp3 = f"mp3_files/{video_id}.mp3"
    audio_file_wav = f"wav_files/{video_id}.wav"

    try:
        print(f"Downloading audio for video {video_id}...")
        result = subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "--output", audio_file_mp3, f"https://www.youtube.com/watch?v={video_id}"],
            check=True,
            text=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp command failed with error:\n{e.stdout}{e.stderr}")
        return None, None

    # Convert mp3 to wav
    try:
        print(f"Converting audio format for video {video_id}...")
        progress_process = subprocess.Popen(
            ["ffmpeg", "-i", audio_file_mp3, "-ar", "16000", "-ac", "1", "-progress", "-", audio_file_wav],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        total_duration = None

        while progress_process.poll() is None:
            line = progress_process.stdout.readline().strip()
            if not line or '=' not in line:
                continue

            key, value = line.split('=')

            if key == 'duration':
                total_duration = float(value)
            elif key == 'out_time_ms' and total_duration:
                current_time = float(value) / 1000000
                progress = current_time / total_duration * 100
                sys.stdout.write(f"\rConverting audio format for video {video_id}: {progress:.2f}%")
                sys.stdout.flush()

        sys.stdout.write("\n")

    except subprocess.CalledProcessError as e:
        print(f"ffmpeg command failed with error:\n{e.stdout}{e.stderr}")
        return None, None

    # Transcribe the audio
    with io.open(audio_file_wav, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )

    try:
        print(f"Transcribing audio for video {video_id}...")
        response = speech_client.recognize(config=config, audio=audio)
    except Exception as e:
        print(f"Transcription failed with error: {e}")
        return None, None

    transcript = "\n".join([result.alternatives[0].transcript for result in response.results])

    return title, transcript

def transcribe_video_to_html(youtube, speech_client, video_id):
    # Transcribe the video
    title, transcript = transcribe_video(youtube, speech_client, video_id)

    if title is None or transcript is None:
        return None, None

    # Generate the HTML file
    html_filename = f"{video_id}.html"
    with open(html_filename, "w") as html_file:
        html_file.write("<html><body><pre>\n")
        html_file.write(transcript)
        html_file.write("</pre></body></html>")

    return title, html_filename


def get_channel_id_from_url(youtube, channel_url):
    custom_url = channel_url.split('/')[-1]
    response = youtube.search().list(
        part='snippet',
        type='channel',
        q=custom_url,
        maxResults=1
    ).execute()

    if 'items' in response and response['items']:
        return response['items'][0]['snippet']['channelId']
    else:
        raise ValueError(f"No channel found for the URL: {channel_url}")

def save_videos_to_csv(youtube, channel_id, csv_file="videos.csv"):
    videos = get_all_videos(youtube, channel_id)

    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Video ID", "Title", "Description", "Published At", "Transcript Link"])

        for video in videos:
            writer.writerow([video["id"], video["title"], video["description"], video["publishedAt"], ""])

def main():
    youtube = build_youtube_service(API_KEY)
    speech_client = build_speech_client(SERVICE_ACCOUNT_FILE)
    channel_id = get_channel_id_from_url(youtube, CHANNEL_URL)
    save_videos_to_csv(youtube, channel_id)

    with open("videos.csv", mode="r", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader]

    with open("videos.csv", mode="w", newline="") as csvfile:
        fieldnames = ["Video ID", "Title", "Description", "Published At", "Transcript Link"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        transcribe_all = False
        for row in rows:
            video_id = row["Video ID"]
            title = row["Title"]

            if not transcribe_all:
                should_transcribe = input(f"Transcribe '{title}'? (y/n/all): ").lower()
                if should_transcribe == "all":
                    transcribe_all = True

            if transcribe_all or should_transcribe == "y":
                title, html_filename = transcribe_video_to_html(youtube, speech_client, video_id)
                row["Transcript Link"] = html_filename

            writer.writerow(row)

if __name__ == "__main__":
    main()
