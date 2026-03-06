import boto3
import os
from PIL import Image
from io import BytesIO

# Get environment variables
INPUT_BUCKET = os.environ['INPUT_BUCKET']
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
INPUT_PREFIX = os.environ.get('INPUT_PREFIX', 'input/')
OUTPUT_PREFIX = os.environ.get('OUTPUT_PREFIX', 'output/')
MAX_WIDTH = int(os.environ.get('MAX_WIDTH', '800'))
MAX_HEIGHT = int(os.environ.get('MAX_HEIGHT', '800'))

s3 = boto3.client('s3', region_name='ap-southeast-2')

def list_input_images():
    response = s3.list_objects_v2(Bucket=INPUT_BUCKET, Prefix=INPUT_PREFIX)
    if 'Contents' not in response:
        print("No files found in input folder")
        return []
    return [obj['Key'] for obj in response['Contents'] 
            if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png'))]

def resize_image(image_bytes, filename):
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail((MAX_WIDTH, MAX_HEIGHT))
    output = BytesIO()
    fmt = 'JPEG' if filename.lower().endswith(('.jpg', '.jpeg')) else 'PNG'
    img.save(output, format=fmt, optimize=True, quality=85)
    output.seek(0)
    return output

def process_images():
    images = list_input_images()
    if not images:
        return
    
    print(f"Found {len(images)} images to process")
    
    for key in images:
        filename = key.split('/')[-1]
        print(f"Processing {filename}...")
        
        # Download from S3
        response = s3.get_object(Bucket=INPUT_BUCKET, Key=key)
        image_bytes = response['Body'].read()
        
        # Resize
        resized = resize_image(image_bytes, filename)
        
        # Upload to output bucket
        output_key = f"{OUTPUT_PREFIX}{filename}"
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=resized,
            ContentType='image/jpeg'
        )
        print(f"Saved resized image to s3://{OUTPUT_BUCKET}/{output_key}")
    
    print(f"Done. Processed {len(images)} images.")

if __name__ == '__main__':
    process_images()