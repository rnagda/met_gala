import os
import io
import pickle
import cv2
from skimage.metrics import structural_similarity as ssim
import numpy as np
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from api_key import OPEN_AI_API_KEY

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
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
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
    
    if not items:
        print('No files found.')
    else:
        print('Files:')
        for item in items:
            print(f"{item['name']} ({item['id']})")
            # Optionally, you can download the file here if needed:
            download_file(service, item['id'], item['name'])

# Function to download the file from Google Drive
def download_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")
    print(f"File {file_name} downloaded successfully.")


def compare_images(image_path1, image_path2, resize_dim=(256, 256)):
    # Read the images
    img1 = cv2.imread(image_path1, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(image_path2, cv2.IMREAD_GRAYSCALE)
    
    # Resize both images to the same dimensions
    img1_resized = cv2.resize(img1, resize_dim)
    img2_resized = cv2.resize(img2, resize_dim)
    
    # Compute the SSIM between the two resized images
    similarity_index, diff = ssim(img1_resized, img2_resized, full=True)
    
    # Output the result
    print(f"Structural Similarity Index (SSIM): {similarity_index}")
    if similarity_index > 0.90:
        print("The images are similar!")
    else:
        print("The images are not similar.")
        

from PIL import Image
import imagehash

def are_images_similar_hash(image_path1, image_path2):
    hash1 = imagehash.average_hash(Image.open(image_path1))
    hash2 = imagehash.average_hash(Image.open(image_path2))
    cutoff = 25  # Adjust as needed
    # print(hash1)
    # print(hash2)
    # print(hash1 - hash2)
    return (hash1 - hash2) <= cutoff

    import cv2

from PIL import Image


def compareGPT2(image_path1, image_path2):
    import torch
    from transformers import CLIPProcessor, CLIPModel
    # Load the CLIP model and processor
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    # Load your images
    image1 = Image.open(image_path1).convert("RGB")
    image2 = Image.open(image_path2).convert("RGB")

    # Preprocess the images
    inputs1 = processor(images=image1, return_tensors="pt")
    inputs2 = processor(images=image2, return_tensors="pt")

    # Get feature vectors (embeddings)
    with torch.no_grad():
        features1 = model.get_image_features(**inputs1)
        features2 = model.get_image_features(**inputs2)

    # Normalize the features
    features1 /= features1.norm(dim=-1, keepdim=True)
    features2 /= features2.norm(dim=-1, keepdim=True)

    # Calculate cosine similarity
    similarity = torch.nn.functional.cosine_similarity(features1, features2).item()

    print(f"Cosine similarity: {similarity:.4f}")

    # Set a threshold for what you consider "the same object"
    if similarity > 0.90:
        print("These images likely depict the same object.")
    else:
        print("These images are likely different.")


import openai
import base64

def compareGPT(image1, image2):

    # Set your OpenAI API key
    # Load your API key
    client = openai.OpenAI(api_key=OPEN_AI_API_KEY)

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



def are_images_similar(image_path1, image_path2):
    img1 = cv2.imread(image_path1, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(image_path2, cv2.IMREAD_GRAYSCALE)

    orb = cv2.ORB_create()
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    matches = sorted(matches, key=lambda x: x.distance)
    match_score = len(matches)

    threshold = 50  # Adjust as needed
    print(match_score)
    return match_score > threshold

# Usage
folder_id = '1fNhPIKcZD1A8hjpy6oVu-84HwZL_8IbxyIJ9Uv7rJ9UVZU9jTYF7Uo-hFonXqhZPJneCp3L2'  # Replace with your Google Drive folder ID
service = authenticate_google_drive()
list_files_in_folder(service, folder_id)
print('Are images 1 and 2 similar')
print(compareGPT('1.jpeg', '2.jpg'))
print('Are images 1 and 3 similar')
print(compareGPT('1.jpeg', '3.jpg'))
print('Are images 1 and 4 similar')
print(compareGPT('1.jpeg', '4.jpeg'))
print('Are images 1 and 5 similar')
print(compareGPT('1.jpeg', '5.jpg'))
print('Are images 2 and 3 similar')
print(compareGPT('2.jpg', '3.jpg'))
print('Are images 2 and 4 similar')
print(compareGPT('2.jpg', '4.jpeg'))
print('Are images 2 and 5 similar')
print(compareGPT('2.jpg', '5.jpg'))
print('Are images 3 and 4 similar')
print(compareGPT('3.jpg', '4.jpeg'))
print('Are images 3 and 5 similar')
print(compareGPT('3.jpg', '5.jpg'))
print('Are images 4 and 5 similar')
print(compareGPT('4.jpeg', '5.jpg'))
