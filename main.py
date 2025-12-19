import argparse
from atlassian import Confluence
import glob
import markdown
import openai
import os
import requests
import subprocess
import json

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
parser.add_argument(
    "--override",
    required=True,
    help="Override existing transcripts and summaries if they exist",
)
args = parser.parse_args()

def test_env_variables():
    # test to make sure env variables are set
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    elif not os.getenv("CONFLUENCE_URL"):
        raise RuntimeError("CONFLUENCE_URL is not set")
    elif not os.getenv("CONFLUENCE_EMAIL"):
        raise RuntimeError("CONFLUENCE_EMAIL is not set")
    elif not os.getenv("CONFLUENCE_API_TOKEN"):
        raise RuntimeError("CONFLUENCE_API_TOKEN is not set")
    elif not os.getenv("ZOOM_ACCOUNT_ID"):
        raise RuntimeError("ZOOM_ACCOUNT_ID is not set")
    elif not os.getenv("ZOOM_CLIENT_ID"):
        raise RuntimeError("ZOOM_CLIENT_ID is not set")
    elif not os.getenv("ZOOM_CLIENT_SECRET"):
        raise RuntimeError("ZOOM_CLIENT_SECRET is not set")


# set OpenAI API key
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

def get_confluence_video_attachments(page_ID: str):
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

def get_zoom_access_token():
    # get zoom access token
    response = requests.post(
        'https://zoom.us/oauth/token',
        params={
            'grant_type': 'account_credentials',
            'account_id': os.getenv("ZOOM_ACCOUNT_ID")
        },
        auth=(os.getenv("ZOOM_CLIENT_ID"), os.getenv("ZOOM_CLIENT_SECRET"))
    )
    response_data = response.json()
    return response_data['access_token']

def get_meeting_recordings(zoom_access_token: str, meeting_ID: str):
    # get zoom meeting recordings
    headers = {
        'Authorization': f'Bearer {zoom_access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.get(
        f'https://api.zoom.us/v2/meetings/{meeting_ID}/recordings',
        headers=headers
    )
    recording_data = response.json()
    return recording_data

def download_zoom_recordings(recording_data, page_directory: str, access_token:str):
    # download zoom recordings
    os.makedirs(f'{page_directory}/downloaded_videos', exist_ok=True) # make a directory for the downloaded videos
    recordings = []
    for recording_file in recording_data['recording_files']:
        if recording_file['file_type'] != 'MP4': # only download video files 
            continue
        filename = f"{recording_data['topic']}_{recording_data['start_time']}"

        # Check if video already exists
        video_path = f'{page_directory}/downloaded_videos/{filename}.mp4'
        if os.path.exists(video_path):
            print(f"Video already exists, skipping: {filename}.mp4")
            recordings.append({
                'title': f"{filename}.mp4",
                'recording_file': recording_file
            })
            continue  # Skip downloading

        recordings.append({
            'title': f"{filename}.mp4",
            'recording_file': recording_file
        })
        print(f"Downloading {filename} ...") 
        download_url = f"{recording_file['download_url']}"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(download_url, headers=headers)

        with open(f'{page_directory}/downloaded_videos/{filename}.mp4', 'wb') as file:
            file.write(response.content)
        print("Done")
    return recordings

def download_videos(page_directory: str, videos: list):
    # download video files
    os.makedirs(f'{page_directory}/downloaded_videos', exist_ok=True) # make a directory for the downloaded videos

    for video in videos:
        if os.path.exists(f'{page_directory}/downloaded_videos/{video["title"]}'):
            print(f"Video already exists, skipping: {video['title']}")
            continue    

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
        audio_file = f'{page_directory}/audio_extractions/{video_basename}.mp3' # add .mp3 extension

        # Check if audio file already exists
        if os.path.exists(audio_file):
            print(f"Audio already exists, skipping: {audio_file}")
            continue
        # Check if audio chunks already exist
        existing_chunks = glob.glob(f'{page_directory}/audio_extractions/{video_basename}_part*.mp3')
        if existing_chunks:
            print(f"Audio chunks already exist, skipping extraction: {video_basename}")
            continue

        print(f"Extracting audio from {video_basename} ...")
        subprocess.run([
            'ffmpeg',
            '-i', video_file,
            '-vn', # no video
            '-ac', '1', # mono audio
            '-ar', '16000', # 16kHz
            '-b:a', '64k', # 64kbps bitrate
            '-f', 'mp3',
            audio_file
        ], check=True)
        print("Done")
    print()

def split_audio_file(audio_path: str, chunk_duration: int = 3000):
    # split audio file into chunks of chunk_duration seconds
    basename = os.path.basename(audio_path).rsplit('.', 1)[0]
    output_pattern = f"{os.path.dirname(audio_path)}/{basename}_part%03d.mp3"

    try:
        subprocess.run([
            'ffmpeg',
            '-i', audio_path,
            '-f', 'segment',
            '-segment_time', str(chunk_duration),
            '-c', 'copy',
            output_pattern
        ], check=True)

        os.remove(audio_path)  # remove the original large file
        print("Done")
    except subprocess.CalledProcessError as e:
        print(f"Error splitting audio file {audio_path}: {e}")

def transcribe_chunks(chunk_files: list):
    all_transcripts = []
    for chunk_file in chunk_files:
        print(f"Transcribing chunk {chunk_file} ...")
        with open(chunk_file, "rb") as f:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        all_transcripts.append(transcript.text)
    return " ".join(all_transcripts)
    
def transcribe_audio(override: bool, page_directory: str):
    # transcribe the audio
    os.makedirs(f'{page_directory}/transcripts', exist_ok=True)

    audio_folder = f'{page_directory}/audio_extractions/'
    transcript_folder = f'{page_directory}/transcripts/'

    for audio_file in os.listdir(audio_folder):
        try:
            if not audio_file.endswith(".mp3"):
                continue

            audio_path = os.path.join(audio_folder, audio_file)
            basename = os.path.basename(audio_file).rsplit('.', 1)[0]
            transcript_file = os.path.join(transcript_folder, f"{basename}.txt")

            # if audio file is larger than 25MB, split into chunks
            if os.path.getsize(audio_path) > 25 * 1024 * 1024:
                print(f"Audio file {audio_file} is larger than 25MB, splitting into chunks ...")
                split_audio_file(audio_path, chunk_duration=3000)  # split into 50 minute chunks
                chunk_files = sorted(glob.glob(f"{os.path.dirname(audio_path)}/{basename}_part*.mp3"))
                transcript_text = transcribe_chunks(chunk_files)

            # if audio file smaller than 25MB, transcribe directly
            else:
                print(f"Transcribing audio from {audio_file} ...")
                if not override:
                    if os.path.exists(transcript_file):
                        print(f"Transcript already exists, skipping: {basename}")
                        continue
                
                with open(audio_path, "rb") as f:
                    transcript = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=f
                    )
                transcript_text = transcript.text

            with open(transcript_file, "w", encoding="utf-8") as output:
                output.write(transcript_text)
            print(f"Transcribed {audio_file} -> {basename}.txt")

        except openai.RateLimitError:
            print("OpenAI rate limit exceeded. Please try again later.")

    print()

def create_summary(override: bool, page_directory: str):
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
        summary_file = os.path.join(summary_folder, f"{basename}.summary.md")

        if not override:
            if os.path.exists(summary_file):
                print(f"Summary already exists, skipping: {basename}")
                continue
        
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        client = openai.OpenAI()
        response = client.responses.create(
            model="gpt-5.2",
            instructions="""You are an assistant that summarizes transcripts of videos. Provide a concise summary of the following transcript.
            Include a key points section that lists the key points discussed in the video as bullet points. The last section should be the whole transcript inserted. 
            Base everything on the transcript provided. Do not make up any information. 
            Create this in markdown format but don't include the markdown code fence.
            """,
            input=transcript_text,
        )

        with open(summary_file, "w", encoding="utf-8") as output:
            output.write(response.output_text)
        print(f"Created summary -> {basename}.summary.md")
    print()

def create_subpage_for_summary(override: bool, page_directory: str, page_ID: str):
    # create a subpage for the summary
    summary_folder = f'{page_directory}/summaries/'
    for summary in os.listdir(summary_folder):
        local_path = os.path.join(summary_folder, summary)
        basename = summary.rsplit('.', 2)[0]
        print(f"Creating subpage for {summary} ...")

        if not override:
            if confluence.get_page_by_title(title=f"{basename} Summary"):
                print(f"Page already exists, skipping: {basename} Summary")
                continue
        
        md_content = open(local_path, "r").read()
        html_content = markdown.markdown(md_content)


        confluence.update_or_create(
            parent_id=page_ID,
            title=f"{basename} AI Transcription Summary",
            body=html_content,
            representation='storage'
        )
        print(f"Created subpage: {basename} AI Transcription Summary")
    print()

def main():
    test_env_variables()
    override = args.override.lower() == 'true'
    # For testing Zoom integration only
    zoom_access_token = get_zoom_access_token()
    recording_data = get_meeting_recordings(zoom_access_token, "89612627128")
    page_directory = './test_download'  # temporary test directory
    recordings = download_zoom_recordings(recording_data, page_directory, zoom_access_token)
    extract_audio(page_directory, recordings)
    transcribe_audio(override, page_directory)
    create_summary(override, page_directory)
    
    """
    page_ID = args.page_id
    page = confluence.get_page_by_id(page_ID)
    page_title = page['title']
    print(f"Page title: {page_title}")
    print()
    page_directory = create_page_directory(page_title)
    videos = get_confluence_video_attachments(page_ID)
    if not videos:
        return
    download_videos(page_directory, videos)
    extract_audio(page_directory, videos)
    transcribe_audio(override, page_directory)
    create_summary(override, page_directory)
    create_subpage_for_summary(override, page_directory, page_ID)
    """
main()
