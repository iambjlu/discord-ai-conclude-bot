from PIL import Image
import os


def split_image(image_path):
    """
    Splits a long image into multiple square images (and one potential remainder).
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # We want squares, so the step size is the width
        step = width
        
        base_name = os.path.splitext(image_path)[0]
        ext = os.path.splitext(image_path)[1]
        
        count = 0
        for y in range(0, height, step):
            # Define the box to crop
            # (left, upper, right, lower)
            box = (0, y, width, min(y + step, height))
            
            cropped_img = img.crop(box)
            
            output_filename = f"{base_name}_{count}{ext}"
            cropped_img.save(output_filename)
            print(f"Saved: {output_filename}")
            count += 1
            
        print(f"Successfully split image into {count} parts.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the image
    image_path = os.path.join(script_dir, "img.jpg")
    split_image(image_path)
