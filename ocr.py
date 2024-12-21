import cv2
import easyocr
import re

# Path to the .webp image file
image_path = 'img/temp_image.webp'

# Initialize the EasyOCR reader (supports English text)
reader = easyocr.Reader(['en'])

# Function to preprocess the image for better OCR results
def preprocess_image(image):
    if len(image.shape) == 2:  # Image is already single-channel (grayscale)
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 2)

    return thresh

# Function to split the image into three equal horizontal sections
def split_image_into_cards(image):
    height, width = image.shape[:2]

    card_1 = image[:, :width // 3]
    card_2 = image[:, width // 3:(2 * width) // 3]
    card_3 = image[:, (2 * width) // 3:]

    return card_1, card_2, card_3

# Function to crop the middle section where the G value is located
def crop_middle_trim_edges(image, vertical_start_ratio=0.82, vertical_end_ratio=0.87, left_trim_ratio=0.05, right_trim_ratio=0.66):
    height, width = image.shape[:2]

    top = int(height * vertical_start_ratio)
    bottom = int(height * vertical_end_ratio)

    left = int(width * left_trim_ratio)
    right = int(width * (1 - right_trim_ratio))

    cropped_image = image[top:bottom, left:right]
    return cropped_image

# Function to enlarge the cropped image
def enlarge_image(image, scale_factor=2.0):
    width = int(image.shape[1] * scale_factor)
    height = int(image.shape[0] * scale_factor)
    enlarged_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
    return enlarged_image

# Function to extract G values using EasyOCR
def extract_g_value(image):
    # Perform OCR using EasyOCR
    ocr_result = reader.readtext(image, detail=0)

    # Iterate through the detected text results
    for text in ocr_result:
        # Replace 'O' with '0' in the OCR text
        corrected_text = text.replace('O', '0')
        corrected_text = corrected_text.replace('o', '0')
        corrected_text = corrected_text.replace('i', '1')
        corrected_text = corrected_text.replace('l', '1')
        corrected_text = corrected_text.replace('I', '1')

        # Use regex to find the G value in the format "G###"
        match = re.search(r'G(\d{1,4})', corrected_text)
        if match:
            g_value = int(match.group(1))
            if 1 <= g_value <= 2000:
                print(f'Result: [ G{g_value} ]')
                return g_value

    # If no valid G value is found, return 9999
    print('Result: [ Special ]')
    return 9999

# Function to save images at each processing step
def save_image(image, filename):
    cv2.imwrite(f'img/{filename}', image)

# Function to find the card with the lowest G value
def find_lowest_g_value(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)

    if image is None:
        print("Error: Unable to load the image.")
        return None

    # Split the image into three cards
    card_1, card_2, card_3 = split_image_into_cards(image)

    # Crop the middle section of each card
    card_1_cropped = crop_middle_trim_edges(card_1)
    card_2_cropped = crop_middle_trim_edges(card_2)
    card_3_cropped = crop_middle_trim_edges(card_3)

    # Enlarge each cropped section for better OCR accuracy
    card_1_enlarged = enlarge_image(card_1_cropped)
    card_2_enlarged = enlarge_image(card_2_cropped)
    card_3_enlarged = enlarge_image(card_3_cropped)

    # Preprocess the enlarged images (grayscale, blur, thresholding)
    card_1_processed = preprocess_image(card_1_enlarged)
    card_2_processed = preprocess_image(card_2_enlarged)
    card_3_processed = preprocess_image(card_3_enlarged)

    # Save the processed (thresholded) images
    save_image(card_1_processed, "card_1_thresholded.png")
    save_image(card_2_processed, "card_2_thresholded.png")
    save_image(card_3_processed, "card_3_thresholded.png")

    # Extract G values from each processed image using EasyOCR
    g_value_1 = extract_g_value(card_1_processed)
    g_value_2 = extract_g_value(card_2_processed)
    g_value_3 = extract_g_value(card_3_processed)

    # Store the G values in a dictionary
    g_values = {
        "Card 1": g_value_1,
        "Card 2": g_value_2,
        "Card 3": g_value_3
    }

    # Filter out None values and find the card with the lowest G value
    valid_g_values = {card: g for card, g in g_values.items() if g is not None}
    if valid_g_values:
        lowest_card = min(valid_g_values, key=valid_g_values.get)
        lowest_g_value = valid_g_values[lowest_card]
        highest_card = max(valid_g_values, key=valid_g_values.get)
        if valid_g_values[highest_card] == 9999 and lowest_g_value < 100:
            print(f"{highest_card} was a special card.")
            return highest_card, lowest_g_value
        else:
            print(f"{lowest_card} has the lowest G value: G{lowest_g_value}")
            return lowest_card, lowest_g_value
    else:
        print("No valid G values found.")
        return None

# Run the script
if __name__ == "__main__":
    find_lowest_g_value(image_path)
