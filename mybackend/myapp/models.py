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
    age = models.PositiveIntegerField("年紀", null=True, blank=True)
    LOOKS_CHOICES = [
        ('S級 (一見難忘)', 'S級 (一見難忘)'),
        ('A級 (出眾)', 'A級 (出眾)'),
        ('B級 (優異)', 'B級 (優異)'),
        ('C級 (中上)', 'C級 (中上)'),
        ('D級 (大眾)', 'D級 (大眾)'),
        ('E級 (較平凡)', 'E級 (較平凡)'),
    ]
    looks = models.CharField("顏值", max_length=20, choices=LOOKS_CHOICES, blank=True, null=True)
    face = models.CharField("臉蛋", max_length=100, blank=True, null=True)
    temperament = models.CharField("氣質", max_length=100, blank=True, null=True)
    PHYSIQUE_CHOICES = [
        ('骨感', '骨感'),
        ('瘦', '瘦'),
        ('瘦有肉', '瘦有肉'),
        ('標準', '標準'),
        ('曲線迷人', '曲線迷人'),
        ('瘦偏肉', '瘦偏肉'),
        ('微肉', '微肉'),
        ('棉花糖', '棉花糖'),
    ]
    physique = models.CharField("體態", max_length=20, choices=PHYSIQUE_CHOICES, blank=True, null=True)
    CUP_CHOICES = [
        ('天然', '天然'),
        ('醫美', '醫美'),
        ('自體醫美', '自體醫美'),
        ('不確定', '不確定'),
    ]
    cup = models.CharField("罩杯", max_length=20, choices=CUP_CHOICES, blank=True, null=True)
    cup_size = models.CharField("罩杯大小", max_length=1, blank=True, null=True)
    SKIN_TEXTURE_CHOICES = [
        ('絲滑', '絲滑'),
        ('還不錯', '還不錯'),
        ('正常', '正常'),
        ('普通', '普通'),
    ]
    skin_texture = models.CharField("膚質", max_length=20, choices=SKIN_TEXTURE_CHOICES, blank=True, null=True)
    SKIN_COLOR_CHOICES = [
        ('白皙', '白皙'),
        ('偏白', '偏白'),
        ('正常黃', '正常黃'),
        ('偏黃', '偏黃'),
        ('健康黑', '健康黑'),
    ]
    skin_color = models.CharField("膚色", max_length=20, choices=SKIN_COLOR_CHOICES, blank=True, null=True)
    MUSIC_CHOICES = [
        ('未詢問', '未詢問'),
        ('無此服務', '無此服務'),
        ('可加值', '可加值 (費用待填)'),
        ('自談', '可加值 (自談)'),
    ]
    music = models.CharField("音樂", max_length=20, choices=MUSIC_CHOICES, blank=True, null=True)
    music_price = models.DecimalField("音樂價格", max_digits=7, decimal_places=2, blank=True, null=True)
    SPORTS_CHOICES = [
        ('未詢問', '未詢問'),
        ('無此服務', '無此服務'),
        ('可加值', '可加值 (費用待填)'),
        ('自談', '可加值 (自談)'),
        ('體含音', '體含音'),
    ]
    sports = models.CharField("體育", max_length=20, choices=SPORTS_CHOICES, blank=True, null=True)
    sports_price = models.DecimalField("體育價格", max_digits=7, decimal_places=2, blank=True, null=True)
    SCALE_CHOICES = [
        ('三光', '三光'),
        ('兩光', '兩光'),
        ('LG', 'LG'),
        ('親', '親'),
        ('舔', '舔'),
        ('伸', '伸'),
        ('摸', '摸'),
        ('磨', '磨'),
    ]
    scale = models.CharField("尺度", max_length=100, blank=True, null=True)
    content = models.TextField("心得", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField("已審核", default=False)

    def __str__(self):
        return f"Review of {self.animal.name} by {self.user.username}"

class PendingAppointment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_appointments')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.animal.name}"

class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE)
    content = models.TextField("筆記內容", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "animal"),)

    def __str__(self):
        return f"Note for {self.animal.name} by {self.user.username}"
