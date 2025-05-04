# D:\bkgg\mybackend\myapp\apps.py

from django.apps import AppConfig
import logging # 建議導入 logging 模組

logger = logging.getLogger(__name__) # 獲取 logger 實例

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    # --- 新增 ready 方法來連接 signals ---
    def ready(self):
        """
        當 Django App 準備就緒時執行。
        這是導入和連接 Signals 的推薦位置。
        """
        try:
            # 在 ready 方法內部導入 signals 模組，
            # 避免在 App 加載完成前過早導入模型或觸發邏輯。
            import myapp.signals
            # 使用 logger 記錄成功信息，比 print 更規範
            logger.info("myapp signals connected successfully.")
            # 或者，如果你還沒設定 logging，可以用 print 確認：
            # print("myapp signals connected.")
        except ImportError:
            logger.warning("myapp.signals could not be imported. Signals might not be connected.")
        except Exception as e:
            # 捕獲其他可能的錯誤
            logger.error(f"Error connecting myapp signals: {e}", exc_info=True)
    # --- ---