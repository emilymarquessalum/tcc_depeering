
from PIL import Image, ImageTk, ImageDraw, ImageFont

def create_text_bubble(
    lines, 
    background="#ffffff", 
    text_color="#000000", 
    font_size=24, 
    underline_wrapping=None, 
    subfolder=None,
    output_filename="text_bubble.png"
):
    """
    Creates a high-resolution PNG image with a custom symmetric-holed rounded border.
    """
    # 1. Load font
    font = None
    font_names = ["arial.ttf", "Helvetica.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    for font_name in font_names:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except IOError:
            continue
    if font is None:
        font = ImageFont.load_default()

    # 2. Define padding
    border_buffer = int(font_size * 0.6) if underline_wrapping else 0
    padding_x = int(font_size * 1.5) + border_buffer
    padding_y = int(font_size * 1.5) + border_buffer
    line_spacing = int(font_size * 0.4)

    # 3. Calculate text dimensions
    temp_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(temp_img)
    
    max_width = 0
    line_heights = []

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        
        line_heights.append(line_height)
        if line_width > max_width:
            max_width = line_width
            
    total_text_height = sum(line_heights) + (line_spacing * (len(lines) - 1)) if lines else 0
    img_width = max_width + (padding_x * 2)
    img_height = total_text_height + (padding_y * 2)

    # 4. Create canvas
    image = Image.new("RGBA", (img_width, img_height), background)
    draw = ImageDraw.Draw(image)

    # 5. Draw the holed/dashed rounded border if requested
    if underline_wrapping:
        border_margin = int(font_size * 0.5)
        xy = [
            (border_margin, border_margin), 
            (img_width - border_margin, img_height - border_margin)
        ]
        
        border_width = max(2, int(font_size * 0.08))
        radius = int(font_size * 0.6)

        # Draw the solid base border first
        draw.rounded_rectangle(
            xy, 
            radius=radius, 
            outline=underline_wrapping, 
            width=border_width
        )

        # Programmatically punch symmetric "holes" using the background color
        # We calculate positions along the flat segments of the box
        hole_size = int(font_size * 0.3)
        
        # Define where the flat edges are (excluding the corners)
        left_x = border_margin
        right_x = img_width - border_margin
        top_y = border_margin
        bottom_y = img_height - border_margin
        
        # Let's punch holes precisely in the center of all 4 segments for perfect symmetry
        mid_x = img_width // 2
        mid_y = img_height // 2

        holes = [
            (mid_x, top_y),     # Top center hole
            (mid_x, bottom_y),  # Bottom center hole
            (left_x, mid_y),    # Left center hole
            (right_x, mid_y)    # Right center hole
        ]

        # Draw the background-colored blocks over the line to create the gaps
        for h_x, h_y in holes:
            draw.rectangle(
                [
                    (h_x - hole_size // 2, h_y - hole_size // 2), 
                    (h_x + hole_size // 2, h_y + hole_size // 2)
                ], 
                fill=background
            )

    # 6. Draw the text lines
    current_y = padding_y
    for i, line in enumerate(lines):
        draw.text((padding_x, current_y), line, fill=text_color, font=font)
        current_y += line_heights[i] + line_spacing

    # 7. Save file
    final_output_filename = os.path.join(starting_folder, subfolder if subfolder else "", output_filename)
    image.save(final_output_filename, "PNG")
    print(f"Success! Saved to {final_output_filename}")
 