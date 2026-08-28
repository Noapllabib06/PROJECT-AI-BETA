import sys
import os

try:
    from paddleocr import PaddleOCR
    import logging
    # Matikan log panjang dari paddle
    logging.getLogger('ppocr').setLevel(logging.ERROR)
except ImportError:
    print("ERROR: Paket 'paddleocr' tidak ditemukan. Harap install dengan: pip install paddlepaddle paddleocr")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("ERROR: Harap berikan path gambar.")
        sys.exit(1)
        
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"ERROR: File tidak ditemukan: {image_path}")
        sys.exit(1)
    
    try:
        # Gunakan bahasa Inggris (en) atau bisa ditambah Indonesia dengan model khusus
        # use_angle_cls memutar gambar otomatis jika terbalik
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        result = ocr.ocr(image_path, cls=True)
        
        text_content = []
        if result and len(result) > 0 and result[0] is not None:
            for line in result[0]:
                # line[1][0] adalah string teks yang dideteksi
                text_content.append(line[1][0])
                
        if not text_content:
            print("Tidak ada teks yang dapat dikenali.")
        else:
            print("\n".join(text_content))
            
    except Exception as e:
        print(f"ERROR: OCR gagal karena: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
