#!/usr/bin/env python3
"""
Generate icon.png untuk plugin Disaster Classifier
Jalankan sekali: python generate_icon.py
Butuh: pip install Pillow
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    import os

    size = 64
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background lingkaran biru
    draw.ellipse([2, 2, 62, 62], fill=(33, 150, 243, 255), outline=(21, 101, 192, 255), width=2)

    # Simbol gelombang (banjir) — garis putih
    for y_off, thick in [(28, 3), (38, 3), (48, 3)]:
        for x in range(8, 57, 8):
            x2 = min(x + 6, 56)
            draw.arc([x, y_off - 4, x2, y_off + 4], start=0, end=180, fill='white', width=thick)

    out_dir = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'icon.png')
    img.save(out_path)
    print(f"Icon berhasil dibuat: {out_path}")

except ImportError:
    # Jika Pillow tidak tersedia, buat icon placeholder minimal
    import struct, zlib, os

    def create_minimal_png(path, size=64):
        """Buat PNG biru solid 64x64 tanpa dependency eksternal."""
        def chunk(name, data):
            c = zlib.crc32(name + data) & 0xffffffff
            return struct.pack('>I', len(data)) + name + data + struct.pack('>I', c)

        ihdr_data = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
        raw_rows  = b''.join(b'\x00' + b'\x21\x96\xF3' * size for _ in range(size))
        idat_data = zlib.compress(raw_rows)

        png = (b'\x89PNG\r\n\x1a\n'
               + chunk(b'IHDR', ihdr_data)
               + chunk(b'IDAT', idat_data)
               + chunk(b'IEND', b''))

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(png)
        print(f"Icon placeholder dibuat: {path}")

    out_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon.png')
    create_minimal_png(out_path)
