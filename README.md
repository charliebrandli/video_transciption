# Confluence Video Transcription

This script:
- finds video attachments on a Cofluence page
- downloads them
- extracts the audio
- transcribes audio to text
- uploads the transcripts back to the same Confluence page as an attachment

## What this script does

The script will:

1. Connect to Confluence using the REST API
2. Find video attachments (ending in: .mp4, .mov, .mkv) on the page
3. Download the videos locally
4. Extract audio from each video using ffmpeg
5. Transcribe the audio to text using OpenAI's Whisper (currently mocked)
6. Upload the transcript files back to the same Confluence page as attachments

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

### Environment variables

```md
### Environment variables

Set the following environment variables:

- `CONFLUENCE_URL`  
  Example: `https://yourcompany.atlassian.net/wiki`

- `CONFLUENCE_EMAIL`  
  Your Atlassian account email

- `CONFLUENCE_API_TOKEN`  
  Confluence API token

- `OPENAI_API_KEY` 

## Output

The script creates the following local directories:

- `downloaded_videos/` – downloaded video files
- `audio/` – extracted WAV audio files
- `transcripts/` – transcript text files

Transcript files are uploaded back to the Confluence page as attachments.

## Notes

- If a file already exists locally, the script will skip reprocessing it.
- Uploaded transcripts appear as page attachments and are not automatically inserted into the page body.
- Confluence may take a short time to show newly uploaded attachments in the UI.

## Development Status

- Video download: complete
- Audio extraction: complete
- Transcription: mocked (replace with Whisper when API quota is available)