# D:\bkgg\mybackend\myapp\utils.py
from .models import UserTitleRule

def get_user_title_from_count(count):
    """
    根據資料庫中定義的 UserTitleRule 取得使用者稱號。
    """
    if not isinstance(count, int) or count < 1:
        return None

    try:
        active_rules = UserTitleRule.objects.filter(is_active=True) # Already ordered by Meta
        for rule in active_rules:
            if count >= rule.min_review_count:
                return rule.title_name
        return None
    except Exception as e:
        print(f"Error fetching UserTitleRule: {e}")
        # Consider logging the error: logger.error(...)
        return None