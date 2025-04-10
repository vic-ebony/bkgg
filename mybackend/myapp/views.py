from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.template.loader import render_to_string
import re
import pytesseract
from PIL import Image
from .models import Animal, Hall, Review, PendingAppointment, Note

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
    if hall_id and hall_id != "all":
        animals = Animal.objects.filter(hall_id=hall_id)
    else:
        animals = Animal.objects.all()
    animals = animals.order_by('-is_exclusive', '-is_hot', '-is_newcomer', 'name')
    animals = animals.annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
    context = {'animals': animals, 'halls': halls}
    
    # 最新評論
    latest_reviews = Review.objects.filter(approved=True).select_related('animal').order_by("-created_at")[:15]
    for review in latest_reviews:
        review.animal.approved_review_count = review.animal.reviews.filter(approved=True).count()
    context['latest_reviews'] = latest_reviews

    if request.user.is_authenticated:
        pending = PendingAppointment.objects.filter(user=request.user).select_related('animal')
        for appointment in pending:
            appointment.animal.approved_review_count = appointment.animal.reviews.filter(approved=True).count()
        context['pending_appointments'] = pending
        pending_ids = [str(appointment.animal.id) for appointment in pending]
        context['pending_ids'] = pending_ids

        user_notes = Note.objects.filter(user=request.user)
        notes_by_animal = {}
        for note in user_notes:
            notes_by_animal[str(note.animal.id)] = note
        context['notes_by_animal'] = notes_by_animal

        my_notes = Note.objects.filter(user=request.user).select_related('animal').order_by("-updated_at")
        for note in my_notes:
            note.animal.approved_review_count = note.animal.reviews.filter(approved=True).count()
        context['my_notes'] = my_notes
    else:
        context['notes_by_animal'] = {}

    if request.GET.get('login_error'):
        context['login_error'] = request.GET.get('login_error')

    # 如果是 AJAX 請求，僅回傳局部班表表格內容
    if request.GET.get('ajax') == '1':
        table_html = render_to_string('partials/daily_animal_tbody.html', {'animals': animals}, request=request)
        return JsonResponse({'table_html': table_html})

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

def format_price(value):
    if value is None:
        return None
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

@login_required
def add_review(request):
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
        return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
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

@login_required
def add_note(request):
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        content = request.POST.get("content", "").strip()
        if not animal_id or not content:
            return JsonResponse({"success": False, "error": "缺少必要資訊"})
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return JsonResponse({"success": False, "error": "找不到該美容師"})
        note, created = Note.objects.get_or_create(
            user=request.user,
            animal=animal,
            defaults={"content": content}
        )
        if not created:
            note.content = content
            note.save()
        return JsonResponse({"success": True, "message": "筆記已儲存", "note_id": note.id})
    return JsonResponse({"success": False, "error": "只允許 POST 請求"})

@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id")
    if not note_id:
        return JsonResponse({"success": False, "error": "缺少筆記 ID"})
    try:
        note = Note.objects.get(id=note_id, user=request.user)
    except Note.DoesNotExist:
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"})
    note.delete()
    return JsonResponse({"success": True, "message": "筆記已刪除"})

@login_required
def update_note(request):
    if request.method == "POST":
        note_id = request.POST.get("note_id")
        content = request.POST.get("content", "").strip()
        if not note_id or not content:
            return JsonResponse({"success": False, "error": "缺少必要資訊"})
        try:
            note = Note.objects.get(id=note_id, user=request.user)
        except Note.DoesNotExist:
            return JsonResponse({"success": False, "error": "筆記不存在或無權限"})
        note.content = content
        note.save()
        return JsonResponse({"success": True, "message": "筆記已更新", "note_content": note.content})
    return JsonResponse({"success": False, "error": "只允許 POST 請求"})

@login_required
def my_notes_json(request):
    notes = Note.objects.filter(user=request.user).select_related('animal').order_by("-updated_at")
    data = [{
         "animal_name": note.animal.name,
         "content": note.content,
         "updated_at": timezone.localtime(note.updated_at).strftime("%Y-%m-%d %H:%M")
    } for note in notes]
    return JsonResponse({"notes": data})

@login_required
def my_notes(request):
    notes = Note.objects.filter(user=request.user).select_related('animal').order_by("-updated_at")
    paginator = Paginator(notes, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {"page_obj": page_obj}
    return render(request, "my_notes.html", context)
