from django.db import models
from django.conf import settings

class Hall(models.Model):
    name = models.CharField("館別名稱", max_length=100)

    def __str__(self):
        return self.name

class Animal(models.Model):
    name = models.CharField("動物名稱", max_length=100)
    height = models.IntegerField("身高", blank=True, null=True)
    weight = models.IntegerField("體重", blank=True, null=True)
    cup_size = models.CharField("罩杯", max_length=5, blank=True, null=True)
    fee = models.IntegerField("台費", blank=True, null=True)
    time_slot = models.CharField(
        "時段",
        max_length=200,
        blank=True,
        help_text="請輸入時段，每個時段用 '.' 隔開，例如：12.13.14.15.16.17.18.19.20"
    )
    hall = models.ForeignKey(Hall, verbose_name="館別", on_delete=models.SET_NULL, null=True, blank=True)
    photo = models.ImageField("照片", upload_to='animal_photos/', blank=True, null=True)
    is_newcomer = models.BooleanField("新人", default=False)
    is_hot = models.BooleanField("熱門", default=False)
    is_exclusive = models.BooleanField("獨家", default=False)
    introduction = models.TextField("介紹", blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def size_display(self):
        if self.height and self.weight and self.cup_size:
            return f"{self.height}.{self.weight}.{self.cup_size}"
        return ""

class Review(models.Model):
    animal = models.ForeignKey(Animal, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField("內容")
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField("已審核", default=False)  # 新增欄位

    def __str__(self):
        return f"Review of {self.animal.name} by {self.user.username}"
