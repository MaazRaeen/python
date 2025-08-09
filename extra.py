import qrcode

data = "https://github.com/MaazRaeen"
qr = qrcode.QRCode(box_size=10, border=4)
qr.add_data(data)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="yellow")
img.save("./downloads+qrcode.png")

print("QR Code saved as qrcode.png")
import os
os.system("open qrcode.png")  # macOS command to open the file
