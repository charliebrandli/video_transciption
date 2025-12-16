import os
from atlassian import Confluence
import requests
import subprocess
import openai

# get OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if openai.api_key is None:
    raise RuntimeError("OPENAI_API_KEY is not set")


# make sure env variables are set
if not os.getenv("CONFLUENCE_URL"):
    raise RuntimeError("CONFLUENCE_URL is not set")

# create Confluence Client
confluence = Confluence(
    url=os.getenv("CONFLUENCE_URL"),
    username=os.getenv("CONFLUENCE_EMAIL"),
    password=os.getenv("CONFLUENCE_API_TOKEN"))

#get page ID
page_ID = 4225499148 # ID of Test Page with video attachments
page = confluence.get_page_by_id(page_ID)
print(f"Page title: {page['title']}")
print()

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

# download video files
os.makedirs('./downloaded_videos', exist_ok=True) # make a directory for the downloaded videos

for video in video_attachments:
    print(f"Downloading {video['title']} ...")  
    download_url = confluence.url + video['_links']['download']
    response = requests.get(download_url, auth=(confluence.username, confluence.password))

    with open(f'./downloaded_videos/{video["title"]}', 'wb') as file:
        file.write(response.content)
    print(f"Done")
print(f"Downloaded {len(video_attachments)} videos")
print()

# extract audio from videos
os.makedirs('./audio_extractions', exist_ok=True) # make a directory for the audio

for video in video_attachments:
    video_file = f'./downloaded_videos/{video["title"]}'
    video_basename = video["title"].split(".")[0] # filename without extension
    audio_file = f'./audio_extractions/{video_basename}.wav' # add .wav extension
    
    if os.path.exists(audio_file):
        print(f"Audio of this video already exists, skipping: {audio_file}")
        continue

    print(f"Extracting audio from {video['title']} ...")
    subprocess.run([
        'ffmpeg',
        '-i', video_file,
        '-ac', '1', # mono audio
        audio_file
    ], check=True)
    print("Done")

# transcribe the audio
# hardcoded for one video file only
os.makedirs('./transcripts', exist_ok=True)

audio_file = './audio_extractions/TedTalk-Karen_Faith.wav'
with open(audio_file, "rb") as f:
    transcript = openai.audio.transcriptions.create(
        model="whisper-1",
        file=f
    )
basename = os.path.basename(audio_file).split(".")[0]
output_file = f"./transcripts/{basename}.txt"

with open(output_file, "w", encoding="utf-8") as out:
    out.write(transcript['text'])

#print(f"Transcribing audio from {video['title']} ...")
