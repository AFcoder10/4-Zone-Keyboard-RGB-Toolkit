from PIL import Image

# Open the PNG image
img = Image.open('icon.png')

# Save as ICO, automatically generating standard icon sizes
img.save('your_icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])