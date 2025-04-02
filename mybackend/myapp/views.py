# views.py
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
import re
import pytesseract
from PIL import Image
from .models import Animal, Hall, Review, PendingAppointment

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
    # 為所有 animal 計算已審核評論數
    animals = animals.annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
    context = {'animals': animals, 'halls': halls}
    # 如果使用者已登入，讀取待約清單資料
    if request.user.is_authenticated:
        pending = PendingAppointment.objects.filter(user=request.user).select_related('animal')
        for appointment in pending:
            appointment.animal.approved_review_count = appointment.animal.reviews.filter(approved=True).count()
        context['pending_appointments'] = pending
        # 將所有待約美容師的 ID 轉為字串傳入模板
        pending_ids = [str(appointment.animal.id) for appointment in pending]
        context['pending_ids'] = pending_ids
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

# 輔助函式：格式化價格，若尾數為 0 則不顯示小數點後數字
def format_price(value):
    if value is None:
        return None
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

@login_required
def add_review(request):
    """
    POST：新增心得評論（所有欄位），預設 approved=False；
    GET：回傳指定動物所有已審核評論（包含所有欄位）。
    """
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        if not animal_id:
            return JsonResponse({"success": False, "error": "缺少 animal_id"})
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return JsonResponse({"success": False, "error": "找不到該動物"})

        age = request.POST.get("age")
        looks = request.POST.get("looks")
        face = ','.join(request.POST.getlist("face"))
        temperament = ','.join(request.POST.getlist("temperament"))
        scale = ','.join(request.POST.getlist("scale"))
        physique = request.POST.get("physique")
        cup = request.POST.get("cup")
        cup_size = request.POST.get("cup_size")
        skin_texture = request.POST.get("skin_texture")
        skin_color = request.POST.get("skin_color")
        music = request.POST.get("music")
        music_price = request.POST.get("music_price")
        sports = request.POST.get("sports")
        sports_price = request.POST.get("sports_price")
        content = request.POST.get("content", "").strip()

        if music_price == "":
            music_price = None
        if sports_price == "":
            sports_price = None

        Review.objects.create(
            animal=animal,
            user=request.user,
            age=age if age else None,
            looks=looks,
            face=face,
            temperament=temperament,
            physique=physique,
            cup=cup,
            cup_size=cup_size,
            skin_texture=skin_texture,
            skin_color=skin_color,
            music=music,
            music_price=music_price,
            sports=sports,
            sports_price=sports_price,
            scale=scale,
            content=content,
            approved=False
        )
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
            "totalCount": Review.objects.filter(user=r.user, approved=True).count(),
            "age": r.age,
            "looks": r.looks,
            "face": r.face,
            "temperament": r.temperament,
            "physique": r.physique,
            "cup": r.cup,
            "cup_size": r.cup_size,
            "skin_texture": r.skin_texture,
            "skin_color": r.skin_color,
            "music": r.music,
            "music_price": format_price(r.music_price),
            "sports": r.sports,
            "sports_price": format_price(r.sports_price),
            "scale": r.scale,
            "content": r.content,
            "created_at": timezone.localtime(r.created_at).strftime("%Y-%m-%d")
        } for r in reviews]
        return JsonResponse({"reviews": data})

@login_required
def add_pending_appointment(request):
    """
    POST：新增待約項目（透過 AJAX 傳入 animal_id）
    """
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        if not animal_id:
            return JsonResponse({"success": False, "error": "缺少動物 ID"})
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return JsonResponse({"success": False, "error": "找不到該動物"})
        if PendingAppointment.objects.filter(user=request.user, animal=animal).exists():
            return JsonResponse({"success": False, "error": "該美容師已在待約清單中"})
        PendingAppointment.objects.create(user=request.user, animal=animal)
        return JsonResponse({"success": True, "message": f"{animal.name} 已加入待約清單"})
    else:
        return JsonResponse({"success": False, "error": "只允許 POST 請求"})

@require_POST
@login_required
def remove_pending(request):
    """
    POST：移除待約項目（透過 AJAX 傳入 animal_id），同步從資料庫刪除待約紀錄。
    """
    animal_id = request.POST.get("animal_id")
    if not animal_id:
        return JsonResponse({"success": False, "error": "缺少動物 ID"})
    try:
        animal = Animal.objects.get(id=animal_id)
    except Animal.DoesNotExist:
        return JsonResponse({"success": False, "error": "找不到該動物"})
    try:
        pending = PendingAppointment.objects.get(user=request.user, animal=animal)
        pending.delete()
        return JsonResponse({"success": True, "message": f"{animal.name} 待約項目已移除"})
    except PendingAppointment.DoesNotExist:
        return JsonResponse({"success": False, "error": "該待約項目不存在"})
