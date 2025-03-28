import re
import pytesseract
from PIL import Image
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q  # 新增匯入
from rest_framework import generics
from .models import Animal, Hall, Review
from .serializers import AnimalSerializer

# 設定 Tesseract 路徑（請根據實際安裝位置調整）
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tessdata_dir_config = r'--tessdata-dir "C:\\Program Files\\Tesseract-OCR\\tessdata"'

def parse_schedule_line(line):
    pattern = r'^(?P<name>[\u4e00-\u9fa5A-Za-z0-9]+)\s+(?P<measurements>\d+/\d+/[A-Z])\s+(?P<fee>\d+)$'
    m = re.match(pattern, line.strip())
    if m:
        return {
            "name": m.group("name"),
            "measurements": m.group("measurements"),
            "fee": m.group("fee")
        }
    return None

def home(request):
    halls = Hall.objects.all()
    hall_id = request.GET.get('hall_id')
    if hall_id:
        animals = Animal.objects.filter(hall_id=hall_id)
    else:
        animals = Animal.objects.all()
    animals = animals.order_by('-is_exclusive', '-is_hot', '-is_newcomer', 'name')
    # 使用 annotate 加入 approved_review_count 屬性
    animals = animals.annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
    context = {'animals': animals, 'halls': halls}
    if request.GET.get('login_error'):
        context['login_error'] = request.GET.get('login_error')
    return render(request, 'index.html', context)

def upload_schedule_image_view(request):
    if request.method == "POST":
        hall_id = request.POST.get("hall")
        if not request.FILES.get("schedule_image"):
            messages.error(request, "請選擇上傳班表圖片")
            return redirect("upload_schedule_image")
        schedule_image = request.FILES["schedule_image"]
        try:
            hall = Hall.objects.get(id=hall_id)
        except Hall.DoesNotExist:
            messages.error(request, "館別不存在")
            return redirect("upload_schedule_image")
        try:
            image = Image.open(schedule_image)
        except Exception as e:
            messages.error(request, f"無法讀取圖片：{e}")
            return redirect("upload_schedule_image")
        try:
            ocr_text = pytesseract.image_to_string(image, lang='chi_sim', config=tessdata_dir_config)
        except pytesseract.pytesseract.TesseractError as e:
            messages.error(request, f"Tesseract OCR 出錯：{e}")
            return redirect("upload_schedule_image")
        lines = ocr_text.splitlines()
        update_results = []
        for line in lines:
            parsed = parse_schedule_line(line)
            if parsed:
                name = parsed["name"]
                measurements = parsed["measurements"]
                fee = parsed["fee"]
                animal_qs = Animal.objects.filter(name__icontains=name)
                matched_animal = animal_qs.first()
                if matched_animal:
                    matched_animal.fee = int(fee)
                    try:
                        height, weight, cup = measurements.split("/")
                        matched_animal.height = int(height)
                        matched_animal.weight = int(weight)
                        matched_animal.cup_size = cup
                    except Exception as e:
                        pass
                    matched_animal.hall = hall
                    matched_animal.save()
                    update_results.append(f"已更新 {matched_animal.name}：三圍 {measurements}, 台費 {fee}")
                else:
                    update_results.append(f"找不到匹配的記錄：{name}")
        if not update_results:
            messages.warning(request, "未能解析到任何班表資料")
        else:
            for res in update_results:
                messages.info(request, res)
        return redirect("upload_schedule_image")
    else:
        halls = Hall.objects.all()
        return render(request, "upload_schedule.html", {"halls": halls})

def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            return redirect('/?login_error=帳號或密碼錯誤')
    return redirect('home')

def user_logout(request):
    logout(request)
    return redirect('home')

@login_required
def add_review(request):
    """
    若使用 POST 提交評論，則新增評論並預設未審核；
    若使用 GET 傳入 animal_id，則回傳該動物所有已審核的評論。
    """
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        content = request.POST.get("content", "").strip()
        if not animal_id:
            return JsonResponse({"success": False, "error": "缺少 animal_id"})
        if not content:
            return JsonResponse({"success": False, "error": "評論內容不能為空"})
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return JsonResponse({"success": False, "error": "找不到該動物"})
        review = Review.objects.create(animal=animal, user=request.user, content=content, approved=False)
        return JsonResponse({
            "success": True,
            "message": "評論已提交，待審核後將顯示"
        })
    elif request.method == "GET":
        animal_id = request.GET.get("animal_id")
        if not animal_id:
            return JsonResponse({"reviews": []})
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return JsonResponse({"reviews": []})
        reviews = animal.reviews.filter(approved=True).order_by("-created_at")
        data = [{
            "user": r.user.first_name or r.user.username,
            "content": r.content,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")
        } for r in reviews]
        return JsonResponse({"reviews": data})
    return JsonResponse({"success": False, "error": "請使用 GET 或 POST 方法"})

# 動物列表 API
class AnimalListAPIView(generics.ListAPIView):
    queryset = Animal.objects.all()
    serializer_class = AnimalSerializer
