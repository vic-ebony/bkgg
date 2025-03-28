import pytesseract
from PIL import Image

# 設置 Tesseract 路徑
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 嘗試開啟圖片並執行 OCR 辨識
try:
    # 設定正確的圖片路徑
    image = Image.open(r"D:\22.jpg")  # 請替換為您要辨識的圖片路徑
    print("圖片加載成功")
except FileNotFoundError:
    print("圖片文件未找到，請確認路徑是否正確")
except Exception as e:
    print(f"無法加載圖片：{e}")

# 使用 pytesseract 進行 OCR 辨識
try:
    ocr_text = pytesseract.image_to_string(image, lang='chi_sim')  # 使用簡體中文語言包
    print("OCR 結果：")
    print(ocr_text)
except NameError:
    print("未成功載入圖片，請檢查圖片路徑")
except pytesseract.pytesseract.TesseractError as e:
    print(f"Tesseract OCR 出錯：{e}")
except Exception as e:
    print(f"處理 OCR 時發生錯誤：{e}")
