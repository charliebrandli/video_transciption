import argparse
from atlassian import Confluence
import openai
import os
import requests
import subprocess

# create an argument parser
parser = argparse.ArgumentParser(
    description="Download Confluence video attachments and upload transcripts of their audio"
)
# add arguments
parser.add_argument(
    "--page-id",
    required=True,
    help="Confluence page ID containing video attachments"
)
args = parser.parse_args()

# test to make sure env variables are set
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is not set")
elif not os.getenv("CONFLUENCE_URL"):
    raise RuntimeError("CONFLUENCE_URL is not set")
elif not os.getenv("CONFLUENCE_EMAIL"):
    raise RuntimeError("CONFLUENCE_EMAIL is not set")
elif not os.getenv("CONFLUENCE_API_TOKEN"):
    raise RuntimeError("CONFLUENCE_API_TOKEN is not set")

# get OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# create Confluence Client
confluence = Confluence(
    url=os.getenv("CONFLUENCE_URL"),
    username=os.getenv("CONFLUENCE_EMAIL"),
    password=os.getenv("CONFLUENCE_API_TOKEN"))

def get_video_attachments(page_ID: str):
    # list all attachments on the page
    attachments = confluence.get_attachments_from_content(page_ID)
    print("Attachments: ")
    for att in attachments['results']:
        print(att['title'])
    print()

    # filter attachments to find video files
    video_extensions = (".mp4", ".mov", ".mkv")

    video_attachments = [att for att in attachments['results'] if att['title'].lower().endswith(video_extensions)]

    print (f"Found {len(video_attachments)} videos: ")
    for video in video_attachments:
        print(video['title'])
    print()

    return video_attachments

def download_videos(videos: list):
    # download video files
    os.makedirs('./downloaded_videos', exist_ok=True) # make a directory for the downloaded videos

    for video in videos:
        print(f"Downloading {video['title']} ...")  
        download_url = confluence.url + video['_links']['download']
        response = requests.get(download_url, auth=(confluence.username, confluence.password))

        with open(f'./downloaded_videos/{video["title"]}', 'wb') as file:
            file.write(response.content)
        print(f"Done")
    print(f"Downloaded {len(videos)} videos")
    print()

def extract_audio(videos: list):
    # extract audio from videos
    os.makedirs('./audio_extractions', exist_ok=True) # make a directory for the audio

    for video in videos:
        video_file = f'./downloaded_videos/{video["title"]}'
        video_basename = video["title"].rsplit(".", 1)[0] # filename without extension
        audio_file = f'./audio_extractions/{video_basename}.wav' # add .wav extension


        if os.path.exists(audio_file):
            print(f"Audio already exists, skipping: {audio_file}")
            continue

        print(f"Extracting audio from {video_basename} ...")
        subprocess.run([
            'ffmpeg',
            '-i', video_file,
            '-ac', '1', # mono audio
            audio_file
        ], check=True)
        print("Done")
    print()

def transcribe_audio():
    # transcribe the audio
    os.makedirs('./transcripts', exist_ok=True)

    audio_folder = './audio_extractions/'
    transcript_folder = './transcripts/'

    for audio_file in os.listdir(audio_folder):
        try:
            if not audio_file.endswith(".wav"):
                continue

            print(f"Transcribing audio from {audio_file} ...")
            audio_path = os.path.join(audio_folder, audio_file)
            basename = os.path.basename(audio_file).rsplit('.', 1)[0]
            transcript_file = os.path.join(transcript_folder, f"{basename}.txt")
        

            if os.path.exists(transcript_file):
                print(f"Transcript already exists, skipping: {basename}")
                continue

            with open(audio_path, "rb") as f:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )

            with open(transcript_file, "w", encoding="utf-8") as output:
                output.write(transcript['text'])
            print(f"Transcribed {audio_file} -> {transcript_file}")

        except openai.RateLimitError:
            print("OpenAI rate limit exceeded. Please try again later.")
    print()
    return transcript_folder
    
def upload_transcripts(transcript_folder, page_ID: str):
    # upload transcripts back to confluence
    for transcript_file in os.listdir(transcript_folder):
        if not transcript_file.endswith(".txt"):
            continue
        
        local_path = os.path.join(transcript_folder, transcript_file)
        print(f"Uploading {transcript_file} to Confluence page {page_ID} ...")

        confluence.attach_file(
            filename=local_path,
            page_id=page_ID,
            title=transcript_file,
            comment="Uploaded by video transcription script"
        )
        
        print("Done")

def main():
    page_ID = args.page_id
    page = confluence.get_page_by_id(page_ID)
    print(f"Page title: {page['title']}")
    print()
    videos = get_video_attachments(page_ID)
    download_videos(videos)
    extract_audio(videos)
    transcript_folder = transcribe_audio()
    upload_transcripts(transcript_folder, page_ID)

main()