from PIL import Image
import os
import sys

def process_photos():
    photos_dir = "photos"
    processed_dir = "photos_processed"
    
    # Create processed directory if it doesn't exist
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
    
    # Process each photo
    for filename in os.listdir(photos_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_path = os.path.join(photos_dir, filename)
            output_path = os.path.join(processed_dir, f"{os.path.splitext(filename)[0]}.jpg")
            
            try:
                # Open and process image
                with Image.open(input_path) as img:
                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Calculate new size while maintaining aspect ratio
                    width, height = img.size
                    max_size = 640
                    ratio = min(max_size/width, max_size/height)
                    new_size = (int(width*ratio), int(height*ratio))
                    
                    # Resize image
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Save with optimized settings
                    img.save(output_path, 'JPEG', quality=85, optimize=True)
                    
                print(f"Processed {filename} -> {os.path.basename(output_path)}")
            
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

if __name__ == "__main__":
    process_photos()
