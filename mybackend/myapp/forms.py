# D:\bkgg\mybackend\myapp\forms.py
from django import forms
from .models import Hall, Animal # Make sure Animal is imported

class MergeTransferForm(forms.Form):
    """
    用於合併美容師資料中間頁面的表單 (簡化版)。
    僅需選擇要合併的重複記錄，目標館別和名字將由此記錄推斷。
    """
    # 要合併的重複記錄：現在是必填項
    duplicate_animal = forms.ModelChoiceField(
        queryset=Animal.objects.none(), # Queryset 在 __init__ 中設置
        label="要合併的重複記錄 (目標身份)", # Updated label
        required=True, # *** 改為必填 ***
        empty_label="--- 請選擇要合併的記錄 ---", # Updated empty label
        widget=forms.Select(attrs={'class': 'vSelectField'}), # Keep using Admin style
        help_text="選擇代表最終狀態的美容師記錄。此記錄的館別和名字將被採用，合併後此記錄將被刪除。" # Updated help text
    )

    # --- target_hall 和 new_name 欄位已移除 ---

    def __init__(self, *args, **kwargs):
        self.animal_original = kwargs.pop('animal_original', None)
        super().__init__(*args, **kwargs)

        # --- 關鍵：設置 duplicate_animal 的 queryset ---
        if self.animal_original:
            # 仍然排除自己，按館別和姓名排序
            self.fields['duplicate_animal'].queryset = Animal.objects.filter(
                is_active=True
            ).exclude(
                pk=self.animal_original.id
            ).order_by('hall__name', 'name').select_related('hall') # Added select_related for efficiency
        else:
             self.fields['duplicate_animal'].queryset = Animal.objects.none()

    # --- clean 方法簡化或移除 ---
    # 我們可以在 view 中做更精確的檢查，移除這裡複雜的驗證
    # def clean(self):
    #     cleaned_data = super().clean()
    #     duplicate = cleaned_data.get('duplicate_animal')
    #
    #     # 驗證1: 重複記錄必須有館別 (這個可以在 view 中檢查)
    #     # if duplicate and not duplicate.hall:
    #     #     self.add_error('duplicate_animal', '選擇的重複記錄缺少館別信息。')
    #
    #     # 驗證2: 不再需要檢查 duplicate.hall == target_hall
    #     # 驗證3: 關於 new_name 衝突的檢查也移到 view 中，因為 new_name 是推斷出來的
    #
    #     return cleaned_data