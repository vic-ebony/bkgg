import re

def extract_stylist_info(line):
    """
    從一行文字中解析美容師資料，格式預設為：
    (數字) 姓名 👙 三圍（格式：數字/數字/字母）
    例如：(30) 艾瑪 👙 155/45/D
    """
    pattern = r'\((\d+)\)\s*([\u4e00-\u9fa5\w]+)\s*👙\s*(\d+)\/(\d+)\/([A-Z])'
    match = re.search(pattern, line)
    if match:
        return {
            "code": match.group(1),
            "name": match.group(2),
            "measurements": f"{match.group(3)}/{match.group(4)}/{match.group(5)}"
        }
    return None

def extract_time_slots(line):
    """
    解析以 ⏰ 開頭的時段資訊行，
    例如：⏰ 03-3、04 會解析成 ['03-3', '04']
    """
    # 確認是否以時鐘 emoji 開頭
    if not line.startswith("⏰"):
        return None
    time_text = line.replace("⏰", "").strip()
    # 使用全形頓號、逗號作分隔符號
    separators = r'[、,，]'
    slots = re.split(separators, time_text)
    return [slot.strip() for slot in slots if slot.strip()]

# 將你提供的班表內容存成一個多行字串（注意：此處省略了一些說明文字，只保留「今日到班美容師」之後的部分）
sample_text = """
🔴重要注意事項🔴⬇️

⚠️「強制」手機、包包一律鎖櫃
⚠️無法配合驗證與東西放置物櫃者，一概不給予消費
⚠️查驗不過，如有預約照算‼️
⚠️客人取消預約，請提早((two))小時放約，逾時罰一台
⚠️7/1起本公司漲價100，所有牌價已修改，牌價已含清潔費

🔥🔥 今日到班美容師 🔥🔥

(30) 艾瑪 👙 155/45/D
萌萌可愛小隻馬大奶奶
⏰ 03

(32) 妍恩 👙 155/48/B  
(nine)(three)年次、活潑甜美可愛小隻馬🈲️酒客
⏰ 03

(29) 跳跳 👙 157/43/C
穿著火辣 有奶尺度超屌 
⏰ 03-3

(30) 麻糬 👙 167/48/D  
(nine)(zero)年次、顏值可愛大奶
(don't touch)視訊🈲️酒客
⏰ 03、04

(29) 可柔 👙157/46/D
尺度大解放、配合度極高愛噴水
(<)預約送無魔🎵(>)
⏰ 03、04

(30) 紅豆(原長春紅豆) 👙 160/46/E 
性感小騷騷 滿滿御姊風
⏰ 03、04、05

(29) 潔心 👙 160/46/E  
真材實料大奶奶、會按摩、配合度極高
⏰ 03、04、05

(29) GIGI 👙158/47/E
妖豔大奶妹，尺度無極限
⏰ 03-3、04

(30) 佩綺 👙 168/48/E
長腿大奶 淫亂人妻初兼職 好想被淫亂
⏰ 04-2

(30) 蕾蕾 👙 155/40/C
服務互動🈵️分、給你滿滿女友FU 
(<)預約送無膜🎵(>)
⏰ 03-2、04、05

(32) 漾漾 👙 153/40/B 
(nine)(four)年次素人無八大經驗
甜美鄰家小女孩、等待哥哥來開發
(<) 預約送🎵 (>)
⏰ 04、05

(30) 天心 👙 168/50/D (emoji)(emoji)(emoji)
素人 (zero) 經驗、白皙清秀、帶點羞澀
⏰ 🈵️

(33) 蘋果 👙163/51/D (emoji)(emoji)(emoji)
高顏年輕漂亮、五官立體深邃
⏰ 🈵️
"""

# 將班表內容按行分割，並解析每筆美容師記錄
records = []
lines = sample_text.splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    # 試著從行中提取美容師基本資料
    stylist = extract_stylist_info(line)
    if stylist:
        # 找尋後續的時段資訊行（一般會在該筆記錄後的幾行出現）
        time_slots = None
        j = i + 1
        while j < len(lines):
            candidate = lines[j].strip()
            # 當候選行以時鐘 emoji 開頭，就視為時段資訊
            if candidate.startswith("⏰"):
                time_slots = extract_time_slots(candidate)
                break
            j += 1
        stylist['time_slots'] = time_slots
        records.append(stylist)
        # 跳過已處理到的行
        i = j + 1
    else:
        i += 1

# 印出解析結果
for rec in records:
    print(f"姓名：{rec['name']}, 三圍：{rec['measurements']}, 時段：{rec['time_slots']}")
