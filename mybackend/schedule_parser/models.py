# D:\bkgg\mybackend\schedule_parser\models.py
from django.db import models
from myapp.models import Hall, Animal # 從 myapp 導入 Hall 和 Animal
from django.utils import timezone

class DailySchedule(models.Model):
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='daily_schedules_records', # 使用不同的 related_name
        verbose_name="館別"
    )
    animal = models.ForeignKey(
        Animal,
        on_delete=models.CASCADE,
        related_name='daily_schedules_records',
        verbose_name="美容師"
    )
    time_slots = models.CharField(
        "今日時段",
        max_length=300,
        blank=True,
        null=True,
        help_text='例如 "14.15.16", "預約滿", "人到再約"'
    )
    # 使用 default 可以在創建時設置，並允許後續更新
    updated_at = models.DateTimeField("更新時間", default=timezone.now)

    class Meta:
        # 同一館、同美容師只應有一條當前記錄
        unique_together = (('hall', 'animal'),)
        ordering = ['hall__order', 'animal__order', 'animal__name']
        verbose_name = "今日班表記錄"
        verbose_name_plural = "今日班表記錄"
        indexes = [
            models.Index(fields=['hall']),
            models.Index(fields=['animal']),
        ]

    def __str__(self):
        hall_name = self.hall.name if self.hall else "未知館別"
        animal_name = self.animal.name if self.animal else "未知美容師"
        return f"{hall_name} - {animal_name} - 時段: {self.time_slots or '未排班'}"

    # 覆蓋 save 以確保 updated_at 更新
    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)