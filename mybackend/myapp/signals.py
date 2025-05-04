# D:\bkgg\mybackend\myapp\signals.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
import logging

# 導入需要用到的模型
# Important: Use try-except for models to prevent server startup error if models change later
try:
    from .models import Review, StoryReview, UserProfile
except ImportError:
    # Handle cases where models might not be ready during initial migrations etc.
    Review = None
    StoryReview = None
    UserProfile = None
    print("WARNING [signals.py]: Could not import models. Signals might not connect correctly yet.")


logger = logging.getLogger(__name__)

# --- 定義獎勵常量 ---
REVIEW_COIN_REWARD = 3
STORY_COIN_REWARD = 1
INITIAL_COIN_GRANT = 10 # 新用戶初始幣值
# --- ---


# --- Signal Handlers ---

# 1. 自動創建 UserProfile
# Only attempt to connect if UserProfile model was imported successfully
if UserProfile:
    @receiver(post_save, sender=settings.AUTH_USER_MODEL)
    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            UserProfile.objects.create(
                user=instance,
                desire_coins=INITIAL_COIN_GRANT
            )
            logger.info(f"UserProfile created for {instance.username} with initial Desire Coins: {INITIAL_COIN_GRANT}")

    @receiver(post_save, sender=settings.AUTH_USER_MODEL)
    def save_user_profile(sender, instance, **kwargs):
        # 確保 profile 存在
        if hasattr(instance, 'profile'):
            try:
                instance.profile.save()
            except Exception as e:
                logger.error(f"Error saving profile for user {instance.username} in save_user_profile signal: {e}", exc_info=True)
        else:
            # Try creating profile if it doesn't exist for some reason
            if UserProfile: # Check again if model exists
                create_user_profile(sender=sender, instance=instance, created=True)
            else:
                logger.error(f"Cannot create UserProfile for {instance.username} because UserProfile model is not available.")

# 2. Review 核准獎勵
# Only connect if Review and UserProfile models are available
if Review and UserProfile:
    @receiver(pre_save, sender=Review)
    def handle_review_pre_save_and_reward(sender, instance, **kwargs):
        original_instance = None
        try:
            if instance.pk:
                original_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist: pass

        approved_changed_to_true = False
        if original_instance:
            if not original_instance.approved and instance.approved:
                approved_changed_to_true = True
                if not instance.approved_at: instance.approved_at = timezone.now()
                logger.info(f"[PRE_SAVE][signals.py] Review {instance.pk}: Approved status changed to True.")
            elif original_instance.approved and not instance.approved:
                instance.approved_at = None
                instance.reward_granted = False
                logger.info(f"[PRE_SAVE][signals.py] Review {instance.pk}: Approved status changed to False.")
        elif instance.approved:
            approved_changed_to_true = True
            if not instance.approved_at: instance.approved_at = timezone.now()
            logger.info(f"[PRE_SAVE][signals.py] Review (New): Created as approved.")

        if approved_changed_to_true and not instance.reward_granted:
            try:
                profile = UserProfile.objects.get(user=instance.user)
                profile.desire_coins = F('desire_coins') + REVIEW_COIN_REWARD
                profile.save(update_fields=['desire_coins'])
                instance.reward_granted = True
                logger.info(f"[PRE_SAVE][signals.py] Review {instance.pk or '(New)'}: Granting +{REVIEW_COIN_REWARD} coins to {instance.user.username}.")
            except UserProfile.DoesNotExist:
                 logger.error(f"[PRE_SAVE][signals.py] UserProfile not found for user {instance.user.username} for Review {instance.pk or '(New)'}")
            except Exception as e:
                 logger.error(f"[PRE_SAVE][signals.py] Error rewarding Review {instance.pk or '(New)'} for {instance.user.username}: {e}", exc_info=True)

# 3. StoryReview 核准獎勵
# Only connect if StoryReview and UserProfile models are available
if StoryReview and UserProfile:
    @receiver(pre_save, sender=StoryReview)
    def handle_story_pre_save_and_reward(sender, instance, **kwargs):
        original_instance = None
        try:
            if instance.pk: original_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist: pass

        approved_changed_to_true = False
        if original_instance:
            if not original_instance.approved and instance.approved:
                approved_changed_to_true = True
                if not instance.approved_at: instance.approved_at = timezone.now()
                if instance.approved_at and not instance.expires_at: instance.expires_at = instance.approved_at + timedelta(hours=24)
                logger.info(f"[PRE_SAVE][signals.py] StoryReview {instance.pk}: Approved change True.")
            elif original_instance.approved and not instance.approved:
                instance.approved_at = None; instance.expires_at = None
                instance.reward_granted = False
                logger.info(f"[PRE_SAVE][signals.py] StoryReview {instance.pk}: Approved change False.")
        elif instance.approved:
            approved_changed_to_true = True
            if not instance.approved_at: instance.approved_at = timezone.now()
            if instance.approved_at and not instance.expires_at: instance.expires_at = instance.approved_at + timedelta(hours=24)
            logger.info(f"[PRE_SAVE][signals.py] StoryReview (New): Created approved.")

        current_approved_at = instance.approved_at or (timezone.now() if approved_changed_to_true else None)
        current_expires_at = instance.expires_at or (current_approved_at + timedelta(hours=24) if current_approved_at else None)
        is_valid_for_reward = (approved_changed_to_true and not instance.reward_granted and current_expires_at and current_expires_at > timezone.now())

        if is_valid_for_reward:
            try:
                profile = UserProfile.objects.get(user=instance.user)
                profile.desire_coins = F('desire_coins') + STORY_COIN_REWARD
                profile.save(update_fields=['desire_coins'])
                instance.reward_granted = True
                logger.info(f"[PRE_SAVE][signals.py] StoryReview {instance.pk or '(New)'}: Granting +{STORY_COIN_REWARD} coins to {instance.user.username}.")
            except UserProfile.DoesNotExist:
                logger.error(f"[PRE_SAVE][signals.py] UserProfile not found for user {instance.user.username} for StoryReview {instance.pk or '(New)'}")
            except Exception as e:
                logger.error(f"[PRE_SAVE][signals.py] Error rewarding StoryReview {instance.pk or '(New)'} for {instance.user.username}: {e}", exc_info=True)
        elif approved_changed_to_true and not instance.reward_granted:
             expiry_status = "Not Set" if not current_expires_at else ("Expired" if current_expires_at <= timezone.now() else "Valid")
             logger.warning(f"[PRE_SAVE][signals.py] StoryReview {instance.pk or '(New)'}: Approved change True but NO reward granted. Reason: reward_granted={instance.reward_granted}, expiry_status={expiry_status} (Expires: {current_expires_at})")