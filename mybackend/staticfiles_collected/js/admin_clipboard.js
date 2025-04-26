// D:\bkgg\mybackend\static\js\admin_clipboard.js

function copyToClipboard(buttonElement, textToCopy) {
    // 優先嘗試現代 Clipboard API
    if (navigator.clipboard && window.isSecureContext) { // isSecureContext 檢查是否為 HTTPS 或 localhost
        navigator.clipboard.writeText(textToCopy).then(function() {
            showCopySuccess(buttonElement);
        }).catch(function(err) {
            console.error('[Clipboard API] 複製失敗: ', err);
            // 如果 Clipboard API 失敗，嘗試舊方法
            fallbackCopyToClipboard(buttonElement, textToCopy);
        });
    } else {
        // 如果不支援 Clipboard API 或不是安全上下文，直接使用舊方法
        console.warn('[Clipboard API] 不支援或非安全上下文，嘗試使用舊方法。');
        fallbackCopyToClipboard(buttonElement, textToCopy);
    }
}

// 舊版複製方法 (備援)
function fallbackCopyToClipboard(buttonElement, text) {
    // 創建一個隱藏的 textarea 元素
    const textArea = document.createElement("textarea");
    textArea.value = text;

    // 避免在可見區域滾動
    textArea.style.position = 'fixed';
    textArea.style.top = '-9999px';
    textArea.style.left = '-9999px';
    textArea.style.opacity = '0'; // 視覺上完全隱藏

    document.body.appendChild(textArea);
    textArea.focus(); // 聚焦元素
    textArea.select(); // 選取文本內容

    let success = false;
    try {
        // 執行複製命令
        success = document.execCommand('copy');
        if (success) {
            showCopySuccess(buttonElement);
        } else {
            console.error('[Fallback] document.execCommand("copy") 返回 false');
            showCopyError(buttonElement, '瀏覽器拒絕複製操作');
        }
    } catch (err) {
        console.error('[Fallback] 複製時發生錯誤: ', err);
        showCopyError(buttonElement, '複製過程中發生錯誤');
    }

    // 從 DOM 中移除臨時元素
    document.body.removeChild(textArea);
}

// 顯示複製成功的反饋
function showCopySuccess(buttonElement) {
    if (buttonElement) {
        const originalText = buttonElement.textContent;
        buttonElement.textContent = '已複製!';
        buttonElement.disabled = true;
        setTimeout(() => {
            // 檢查按鈕是否還存在於 DOM 中
            if (document.body.contains(buttonElement)) {
                buttonElement.textContent = originalText;
                buttonElement.disabled = false;
            }
        }, 1500); // 1.5秒後恢復按鈕文字和狀態
    }
}

// 顯示複製失敗的錯誤訊息
function showCopyError(buttonElement, message = '複製失敗') {
     alert(message + '，請嘗試手動選取複製。');
     // 可以選擇性地改變按鈕樣式提示錯誤，但 alert 通常足夠
     if (buttonElement) {
         // 恢復按鈕狀態，以便用戶可以再次嘗試（雖然可能還是會失敗）
         buttonElement.disabled = false;
     }
}

// 可以在這裡加入其他 Admin 頁面可能需要的全局 JS
console.log("admin_clipboard.js with fallback loaded."); // 確認腳本已加載