import base64
import os
import io
import json
import pickle
import pyheif
import openai
import subprocess

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from PIL import Image


# If modifying the folder scope, update the SCOPES.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
image_path2 = '2.jpg'

# Authenticate and build the Google Drive service
def authenticate_google_drive():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    creds_path = "credentials.json"
    with open(creds_path, "w") as f:
        json.dump(json.loads(os.environ["GOOGLE_CREDS_JSON"]), f)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(os.getenv("GOOGLE_CREDS_JSON")),
                scopes=SCOPES
            )
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service

# Function to list files in a specific Google Drive folder
def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query, spaces='drive').execute()
    items = results.get('files', [])
    files = []
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print(f"{item['name']} ({item['id']})")
            files.append({'name': item['name'], 'id': item['id']})
            # Optionally, you can download the file here if needed:
            # download_file(service, item['id'], item['name'])
    return files

def authenticate_google_sheet():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(os.getenv("GOOGLE_CREDS_JSON")),
                scopes=SCOPES
            )
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)
    return service

def parse_google_sheet(service):
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId='1NdEXW-DIakyGy6sW6bKayzSOlW4XPlJTSegQ9rltkaQ', range='Form Responses 1!A2:E').execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
        return []

    return values


def convert_heic_to_jpg_cli(input_path, output_path):
    image = Image.open(input_path)
    image.save(output_path, format="JPEG")
    return output_path

def download_and_convert(service, file_id, file_name):
    # Step 1: Download the file
    request = service.files().get_media(fileId=file_id)

    # Ensure the submissions folder exists
    os.makedirs("submissions", exist_ok=True)

    # Then download the file
    file_path = os.path.join("submissions", file_name)
    fh = io.FileIO(file_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")

    print(f"File {file_name} downloaded successfully.")

    # Step 2: Convert to JPG if it's a HEIC file
    if file_name.lower().endswith('.heic'):
        from pathlib import Path
        output_path = file_path.replace('.heic', '.jpg')
        print(file_path)
        converted_path = convert_heic_to_jpg_cli(file_path, output_path)
        if converted_path:
            print(f"Converted to JPG: {converted_path}")
            # Optional: delete the original .heic file
            Path(file_path).unlink()
        return converted_path
    else:
        return file_path


def compareGPT(image1, image2):

    # Set your OpenAI API key
    # Load your API key
    client = openai.OpenAI(api_key=os.environ.get('OPEN_AI_API_KEY'))

    def encode_image(image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # Encode images
    image1_base64 = encode_image(image1)
    image2_base64 = encode_image(image2)

    # Make a GPT-4 Vision request
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Are these two images of the same object?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image1_base64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image2_base64}"}}
                ]
            }
        ],
        max_tokens=100,
    )

    print(response.choices[0].message.content)
    return response.choices[0].message.content 


# Usage
# folder_id = '1fNhPIKcZD1A8hjpy6oVu-84HwZL_8IbxyIJ9Uv7rJ9UVZU9jTYF7Uo-hFonXqhZPJneCp3L2'  # Replace with your Google Drive folder ID
# service = authenticate_google_drive()
# list_files_in_folder(service, folder_id)
# print('Are images 1 and 2 similar')
# print(compareGPT('1.jpeg', '2.jpg'))
# print('Are images 1 and 3 similar')
# print(compareGPT('1.jpeg', '3.jpg'))
# print('Are images 1 and 4 similar')
# print(compareGPT('1.jpeg', '4.jpeg'))
# print('Are images 1 and 5 similar')
# print(compareGPT('1.jpeg', '5.jpg'))
# print('Are images 2 and 3 similar')
# print(compareGPT('2.jpg', '3.jpg'))
# print('Are images 2 and 4 similar')
# print(compareGPT('2.jpg', '4.jpeg'))
# print('Are images 2 and 5 similar')
# print(compareGPT('2.jpg', '5.jpg'))
# print('Are images 3 and 4 similar')
# print(compareGPT('3.jpg', '4.jpeg'))
# print('Are images 3 and 5 similar')
# print(compareGPT('3.jpg', '5.jpg'))
# print('Are images 4 and 5 similar')
# print(compareGPT('4.jpeg', '5.jpg'))
