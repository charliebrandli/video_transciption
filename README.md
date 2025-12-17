# Confluence Video Transcription

This script:
- finds video attachments on a Cofluence page
- downloads them
- extracts the audio
- transcribes audio to text
- summarizes the transcript and extracts the key points of the video
- uploads the summaries back onto Confluence

## What this script does

Given a Confluence page ID, the script will:

1. Connect to Confluence using the REST API
2. Find video attachments (ending in: .mp4, .mov, .mkv) on the page
3. Download the videos locally
4. Extract audio from each video using ffmpeg
5. Transcribe the audio to text using OpenAI's Whisper 
6. Summarize the transcript using OpenAI's Response
7. Upload the summary files back to Confluence as subpages of the original page

## Requirements

- Python 3.9+
- ffmpeg installed and available in PATH
- Confluence Cloud account with acces to the target page
- Confluence API token
- OpenAI API key for transcription

## Setup

1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies:

```bash
pip install -r requirements.txt
```

### Environment variables

Set the following environment variables:

```bash
export CONFLUENCE_URL="<https://yourcompany.atlassian.net/wiki>"
export CONFLUENCE_EMAIL="<Your Atlassian account email>"
export CONFLUENCE_API_TOKEN="<Confluence API token>"
export OPENAI_API_KEY="<OpenAI API key>"
```

## Usage

Run the script by providing a Confluence page ID:

```bash
python main.py --page-id 123456789
```

## Output

The script creates the following local directories:

- `pages/<page_title>/` - subfolder for the page the script is run on
- `downloaded_videos/` – downloaded video files
- `audio_extractions/` – extracted WAV audio files
- `transcripts/` – transcript text files
- `summaries/` - summary text files

Transcript files are uploaded to Confluence as subpages

## Notes

- If an audio file already exists locally, the script will skip reprocessing it.
- Uploaded transcripts appear as subpages under the original page.

## Development Status

- Video download: complete
- Audio extraction: complete
- Transcription: complete
- Summarization: complete