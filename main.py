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

def create_page_directory(page_title: str):
    os.makedirs('./pages', exist_ok=True) # make a directory for the pages
    # create a directory for the page
    page_directory = f'./pages/{page_title.replace(" ", "_")}'
    os.makedirs(page_directory, exist_ok=True)
    return page_directory

def get_video_attachments(page_ID: str):
    # list all attachments on the page
    attachments = confluence.get_attachments_from_content(page_ID)
    print("Attachments: ")
    for att in attachments['results']:
        print(att['title'])
    print()

    # filter attachments to find video files
    video_extensions = (".mp4", ".mov", ".mkv") #TODO: Check if this is all the attachments we use

    video_attachments = [att for att in attachments['results'] if att['title'].lower().endswith(video_extensions)]

    if not video_attachments:
        print("No video attachments found. Exiting.")
        return

    print (f"Found {len(video_attachments)} videos: ")
    for video in video_attachments:
        print(video['title'])
    print()

    return video_attachments

def download_videos(page_directory: str, videos: list):
    # download video files
    os.makedirs(f'{page_directory}/downloaded_videos', exist_ok=True) # make a directory for the downloaded videos

    for video in videos:
        print(f"Downloading {video['title']} ...")  
        download_url = confluence.url + video['_links']['download']
        response = requests.get(download_url, auth=(confluence.username, confluence.password))

        with open(f'{page_directory}/downloaded_videos/{video["title"]}', 'wb') as file:
            file.write(response.content)
        print(f"Done")
    print(f"Downloaded {len(videos)} videos")
    print()

def extract_audio(page_directory: str, videos: list):
    # extract audio from videos
    os.makedirs(f'{page_directory}/audio_extractions', exist_ok=True) # make a directory for the audio

    for video in videos:
        video_file = f'{page_directory}/downloaded_videos/{video["title"]}'
        video_basename = video["title"].rsplit(".", 1)[0] # filename without extension
        audio_file = f'{page_directory}/audio_extractions/{video_basename}.wav' # add .wav extension


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

def transcribe_audio(page_directory: str, mock=False):
    # transcribe the audio
    os.makedirs(f'{page_directory}/transcripts', exist_ok=True)

    audio_folder = f'{page_directory}/audio_extractions/'
    transcript_folder = f'{page_directory}/transcripts/'

    for audio_file in os.listdir(audio_folder):
        try:
            if not audio_file.endswith(".wav"):
                continue

            print(f"Transcribing audio from {audio_file} ...")
            audio_path = os.path.join(audio_folder, audio_file)
            basename = os.path.basename(audio_file).rsplit('.', 1)[0]
            transcript_file = os.path.join(transcript_folder, f"{basename}.txt")

            if not mock:
                if os.path.exists(transcript_file):
                    print(f"Transcript already exists, skipping: {basename}")
                    continue
                
                with open(audio_path, "rb") as f:
                    transcript = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=f
                    )
                transcript_text = transcript.text

            else:
                transcript_text = f"TEMPORARY MOCK TRANSCRIPT for {basename}"

            with open(transcript_file, "w", encoding="utf-8") as output:
                output.write(transcript_text)
            print(f"Transcribed {audio_file} -> {basename}.txt")

        except openai.RateLimitError:
            print("OpenAI rate limit exceeded. Please try again later.")
    print()
    
def create_summary(page_directory: str):
    # create a summary of the transcript
    os.makedirs(f'{page_directory}/summaries', exist_ok=True)
    summary_folder = f'{page_directory}/summaries/'
    transcript_folder = f'{page_directory}/transcripts/'

    for transcript_file in os.listdir(transcript_folder):
        if not transcript_file.endswith(".txt"):
            continue

        print(f"Creating summary for {transcript_file} ...")
        transcript_path = os.path.join(transcript_folder, transcript_file)
        basename = transcript_file.rsplit('.', 1)[0]
        summary_file = os.path.join(summary_folder, f"{basename}.summary.txt")

        if os.path.exists(summary_file):
            print(f"Summary already exists, skipping: {basename}")
            continue
        
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        client = openai.OpenAI()
        response = client.responses.create(
            model="gpt-4.1",
            instructions="""You are an assistant that summarizes transcripts of videos. Provide a concise summary of the following transcript.
            Include a section that lists the key points discussed in the video as bullet points. The last section should be the whole transcript inserted. Base everything on the transcript provided. Do not make up any information.
            """,
            input=transcript_text,
        )

        with open(summary_file, "w", encoding="utf-8") as output:
            output.write(response.output_text)
        print(f"Created summary -> {basename}.summary.txt")
    print()

def create_subpage_for_summary(page_directory: str, page_ID: str, page_space_key: str):
    # create a subpage for the summary
    summary_folder = f'{page_directory}/summaries/'
    for summary in os.listdir(summary_folder):
        if not summary.endswith(".txt"):
            continue
        
        local_path = os.path.join(summary_folder, summary)
        basename = summary.rsplit('.', 2)[0]
        print(f"Creating subpage for {summary} ...")

        if confluence.get_page_by_title(space=page_space_key, title=f"{basename} Summary"):
            print(f"Page already exists, skipping: {basename} Summary")
            continue

        confluence.create_page(
            space=page_space_key,
            title=f"{basename} Summary",
            body=open(local_path, "r").read(),
            parent_id=page_ID
        )
        print("Done")
    print()

def main():
    page_ID = args.page_id
    page = confluence.get_page_by_id(page_ID)
    page_space_key = page['space']['key']
    page_title = page['title']
    print(f"Page title: {page_title}")
    print()
    page_directory = create_page_directory(page_title)
    videos = get_video_attachments(page_ID)
    if not videos:
        return
    download_videos(page_directory, videos)
    extract_audio(page_directory, videos)
    transcribe_audio(page_directory)
    create_summary(page_directory)
    create_subpage_for_summary(page_directory, page_ID, page_space_key)

main()
