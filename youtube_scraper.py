import os
import io
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

def get_file_size(file_path):
    return os.stat(file_path).st_size

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

def get_authenticated_services():
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    speech_client = speech.SpeechClient(credentials=credentials)
    return youtube, speech_client

def get_video_ids(youtube, channel_id):
    video_ids = []
    page_token = None
    while True:
        request = youtube.search().list(
            part='id',
            channelId=channel_id,
            type='video',
            maxResults=50,
            pageToken=page_token
        )
        response = request.execute()
        video_ids.extend([item['id']['videoId'] for item in response['items']])
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return video_ids

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    storage_client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

import os
import sys
import time

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

def main():
    os.makedirs("webm_files", exist_ok=True)
    os.makedirs("wav_files", exist_ok=True)

    channel_url = 'https://www.youtube.com/@StrategyU'

    youtube, speech_client = get_authenticated_services()
    channel_id = get_channel_id_from_url(youtube, channel_url)
    video_ids = get_video_ids(youtube, channel_id)

    for video_id in video_ids:
        title, transcript = transcribe_video(youtube, speech_client, video_id)
        if title is not None and transcript is not None:
            print(f"{title}: {transcript}")
        else:
            print(f"Failed to transcribe video ID {video_id}")

if __name__ == '__main__':
    main()
