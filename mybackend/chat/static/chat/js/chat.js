// D:\bkgg\mybackend\chat\static\chat\js\chat.js (修正並確認完整版)

document.addEventListener('DOMContentLoaded', function() {
    // 確保 USER_ID 已在 HTML 中由 Django 模板定義
    // 並且用戶已登入 (USER_ID 不是 null)
    if (typeof USER_ID === 'undefined' || USER_ID === null) {
        console.log("用戶未登入，聊天功能已禁用。");
        const chatToggleButton = document.getElementById('chat-toggle-button');
        if (chatToggleButton) {
            chatToggleButton.style.display = 'none'; // 如果未登入，隱藏按鈕
        }
        return; // 停止執行聊天相關腳本
    }

    // --- DOM 元素引用 ---
    const chatPanel = document.getElementById('chat-panel');
    const chatToggleButton = document.getElementById('chat-toggle-button');
    const chatCloseButton = chatPanel?.querySelector('.chat-close-button');
    const chatMessages = document.getElementById('chat-messages');
    const chatMessageInput = document.getElementById('chat-message-input');
    const chatMessageSubmit = document.getElementById('chat-message-submit');
    const chatUnreadIndicator = document.getElementById('chat-unread-indicator');

    // 檢查核心元素是否存在
    if (!chatPanel || !chatToggleButton || !chatCloseButton || !chatMessages || !chatMessageInput || !chatMessageSubmit || !chatUnreadIndicator) {
        console.error("聊天室 UI 的一個或多個核心元素未找到，功能可能異常。請檢查 HTML 結構。");
        // 可以選擇在這裡 return，如果缺少核心元素則無法繼續
        // return;
    }

    // --- 狀態變數 ---
    let chatSocket = null;
    let isChatOpen = false;
    let hasUnread = false;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectDelay = 5000; // ms

    // --- 輔助函數 ---

    /**
     * 安全地將 ISO 8601 時間戳格式化為本地時間字串 (HH:MM)。
     * @param {string} isoTimestamp - ISO 8601 格式的時間戳字串。
     * @returns {string} 格式化後的時間字串，或在出錯時返回空字串。
     */
    function formatTimestamp(isoTimestamp) {
        try {
            if (!isoTimestamp) return '';
            return new Date(isoTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            console.error("格式化時間戳時出錯:", e);
            return '';
        }
    }

    /**
     * 將聊天訊息容器捲動到底部。
     */
    function scrollToBottom() {
        if (chatMessages) {
            // 使用 setTimeout 確保 DOM 更新完成後再捲動
            setTimeout(() => {
                try { // 添加 try-catch 以防 chatMessages 在異步操作中失效
                     chatMessages.scrollTop = chatMessages.scrollHeight;
                } catch(e) {
                    console.error("滾動聊天窗口時出錯:", e);
                }
            }, 0);
        }
    }

    /**
     * 將一條訊息添加到聊天顯示區域。
     * @param {object} data - 包含訊息內容的物件，格式應為 {type: 'system'|'user', message: string, username?: string, user_id?: number, timestamp: string}。
     */
    function addChatMessage(data) {
        if (!chatMessages || !data || !data.type || data.message === undefined || data.message === null) { // 確保 message 存在，即使是空字串
            console.warn("收到了無效或不完整的訊息數據，無法顯示:", data);
            return;
        }

        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message');
        const messageTime = formatTimestamp(data.timestamp || new Date().toISOString()); // 提供預設時間戳

        // --- 處理系統訊息 ---
        if (data.type === 'system') {
            messageElement.classList.add('system');
            messageElement.textContent = `[${messageTime}] ${data.message}`;
        }
        // --- 處理用戶訊息 ---
        else if (data.type === 'user') {
            if (data.user_id === undefined || data.username === undefined) {
                console.warn("收到的用戶訊息缺少 user_id 或 username:", data);
                return; // 缺少必要資訊，不顯示
            }
            messageElement.classList.add('user');
            const isMine = data.user_id === USER_ID;
            if (isMine) {
                messageElement.classList.add('mine');
            }

            // Header (Username)
            const usernameSpan = document.createElement('span');
            usernameSpan.className = 'chat-message-header';
            usernameSpan.textContent = data.username || '匿名'; // 預設為匿名
            messageElement.appendChild(usernameSpan);

            // Message Content (Use textContent for security)
            const messageSpan = document.createElement('span');
             // 檢查 message 是否為 null 或 undefined，如果是則顯示空字串
            messageSpan.textContent = (data.message === null || data.message === undefined) ? '' : data.message;
            messageElement.appendChild(messageSpan);

            // Timestamp
            const timeSpan = document.createElement('span');
            timeSpan.className = 'chat-message-time';
            timeSpan.textContent = messageTime;
            messageElement.appendChild(timeSpan);

        }
        // --- 處理未知類型的訊息 ---
        else {
            console.warn("收到了未知的訊息類型:", data.type);
            return; // 不顯示未知類型的訊息
        }

        try {
            chatMessages.appendChild(messageElement);
            scrollToBottom();
        } catch(e) {
             console.error("添加到聊天窗口時出錯:", e);
        }


        // 更新未讀提示 (僅對非系統訊息，且聊天窗口關閉時)
        if (!isChatOpen && data.type === 'user') {
            hasUnread = true;
            if (chatUnreadIndicator) {
                chatUnreadIndicator.style.display = 'block';
            }
        }
    }

    /**
     * 將輸入框中的訊息通過 WebSocket 發送出去。
     */
    function sendMessage() {
        if (!chatMessageInput || !chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
            console.error("無法發送訊息：輸入框丟失或連接未打開。");
            addChatMessage({ type: 'system', message: '錯誤：無法發送訊息，連接已斷開。', timestamp: new Date().toISOString() });
            return;
        }
        const message = chatMessageInput.value.trim();
        if (message) { // 確保有訊息內容
            console.log('正在發送訊息:', message);
            try {
                chatSocket.send(JSON.stringify({
                    'message': message
                }));
                chatMessageInput.value = ''; // 清空輸入框
            } catch (error) {
                console.error("發送訊息時出錯:", error);
                addChatMessage({ type: 'system', message: `發送訊息失敗: ${error.message}`, timestamp: new Date().toISOString() });
            }
        }
        // 重新聚焦輸入框
        chatMessageInput.focus();
    }

    /**
     * 建立或重新建立 WebSocket 連接。
     */
    function connectChatSocket() {
        // 防止同時進行多個連接嘗試
        if (chatSocket && (chatSocket.readyState === WebSocket.CONNECTING || chatSocket.readyState === WebSocket.OPEN)) {
            console.log("WebSocket 連接嘗試被跳過：已存在連接中或已打開的連接。");
            return;
        }

        // 在重新連接前，確保關閉舊的、已關閉或正在關閉的連接實例
        if (chatSocket && (chatSocket.readyState === WebSocket.CLOSED || chatSocket.readyState === WebSocket.CLOSING)) {
             console.log("重新連接前關閉舊的 WebSocket 實例。");
             // 移除舊的事件監聽器，避免內存洩漏 (雖然 close 通常會處理)
             chatSocket.onopen = null;
             chatSocket.onmessage = null;
             chatSocket.onclose = null;
             chatSocket.onerror = null;
             chatSocket.close();
             chatSocket = null;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsURL = `${wsProtocol}//${window.location.host}/ws/chat/`;

        console.log(`嘗試連接 WebSocket: ${wsURL} (嘗試次數: ${reconnectAttempts + 1})`);
        if (chatMessages) { // 僅在面板存在時添加提示
             addChatMessage({ type: 'system', message: `正在連接聊天室... (嘗試 ${reconnectAttempts + 1})`, timestamp: new Date().toISOString() });
        }
        // 禁用輸入和發送按鈕
        if (chatMessageInput) chatMessageInput.disabled = true;
        if (chatMessageSubmit) chatMessageSubmit.disabled = true;

        try {
             chatSocket = new WebSocket(wsURL);
        } catch (error) {
            console.error("創建 WebSocket 實例失敗:", error);
            handleConnectionError(); // 觸發錯誤處理
            return;
        }


        // --- WebSocket 事件處理程序 ---

        chatSocket.onopen = function(e) {
            console.log('WebSocket 連接成功建立。');
            reconnectAttempts = 0; // 重置重連次數
            if (chatMessageInput) chatMessageInput.disabled = false; // 啟用輸入
            if (chatMessageSubmit) chatMessageSubmit.disabled = false; // 啟用發送
            addChatMessage({ type: 'system', message: '已連接到聊天室。', timestamp: new Date().toISOString() });
            // 可選：如果需要在重連時清空歷史記錄，取消下面註解
            // if (chatMessages) chatMessages.innerHTML = '';
            // TODO: 如果需要載入歷史記錄，可以在這裡發送請求
        };

        chatSocket.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                // console.log('從伺服器收到訊息:', data); // Debug: 打印收到的原始數據
                addChatMessage(data); // 添加到聊天窗口
            } catch (error) {
                console.error("解析伺服器訊息數據時出錯:", error, "原始數據:", e.data);
            }
        };

        chatSocket.onclose = function(e) {
            console.error('WebSocket 連接已關閉。 代碼:', e.code, '原因:', e.reason, '是否正常關閉:', e.wasClean);
             if (chatMessageInput) chatMessageInput.disabled = true;
            if (chatMessageSubmit) chatMessageSubmit.disabled = true;

            const currentSocket = this; // 保存當前 socket 引用

            // 清除可能存在的舊監聽器 (以防萬一)
            currentSocket.onopen = null;
            currentSocket.onmessage = null;
            currentSocket.onclose = null;
            currentSocket.onerror = null;

            chatSocket = null; // 清除全局引用，表示當前無有效連接

            // 如果不是正常關閉 (code 1000) 且未達最大重連次數
            if (e.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                console.log(`準備在 ${reconnectDelay / 1000} 秒後嘗試重新連接... (嘗試 ${reconnectAttempts}/${maxReconnectAttempts})`);
                addChatMessage({ type: 'system', message: `連接斷開，${reconnectDelay / 1000}秒後嘗試重新連接...`, timestamp: new Date().toISOString() });
                setTimeout(connectChatSocket, reconnectDelay);
            } else if (e.code === 1000) {
                 addChatMessage({ type: 'system', message: '與聊天室的連接已關閉。', timestamp: new Date().toISOString() });
                 console.log("WebSocket 連接正常關閉。");
            } else {
                 addChatMessage({ type: 'system', message: '嘗試重新連接失敗，請稍後手動重試。', timestamp: new Date().toISOString() });
                 console.log("達到最大重連次數，停止重連。");
            }
        };

        chatSocket.onerror = function(err) {
            console.error('WebSocket 發生錯誤:', err);
             addChatMessage({ type: 'system', message: '發生連接錯誤，請檢查網絡或稍後重試。', timestamp: new Date().toISOString() });
             // onerror 後通常會觸發 onclose，讓 onclose 處理重連邏輯
             // 確保 UI 禁用
             if (chatMessageInput) chatMessageInput.disabled = true;
             if (chatMessageSubmit) chatMessageSubmit.disabled = true;
             // 如果需要立即嘗試關閉
             // handleConnectionError();
        };
    }

     /** 處理連接錯誤或意外關閉時的清理 */
     function handleConnectionError() {
         console.log("執行 handleConnectionError 清理...");
         if (chatMessageInput) chatMessageInput.disabled = true;
         if (chatMessageSubmit) chatMessageSubmit.disabled = true;
         if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED && chatSocket.readyState !== WebSocket.CLOSING) {
            console.log("嘗試關閉錯誤的 WebSocket 連接...");
            chatSocket.onerror = null; // 避免在關閉時觸發更多錯誤處理
            chatSocket.onclose = null; // 避免觸發重連邏輯
            chatSocket.close();
         }
         chatSocket = null; // 清除引用
         // 注意：重連邏輯現在由 onclose 控制
     }

    // --- UI 事件監聽器設定 ---

    if (chatToggleButton) {
        chatToggleButton.addEventListener('click', () => {
            console.log("Chat toggle button CLICKED!"); // <<<--- 添加日誌確認點擊事件觸發
            if (!chatPanel) return;
            isChatOpen = !isChatOpen;
            chatPanel.classList.toggle('open', isChatOpen);

            if (isChatOpen) {
                console.log("Chat panel 打開。");
                if (chatUnreadIndicator) {
                    chatUnreadIndicator.style.display = 'none';
                }
                hasUnread = false;
                scrollToBottom();
                if (chatMessageInput) {
                    chatMessageInput.focus();
                }
                // 檢查連接狀態，只在需要時連接
                if (!chatSocket || chatSocket.readyState === WebSocket.CLOSED || chatSocket.readyState === WebSocket.CLOSING) {
                    console.log("面板打開，嘗試連接 WebSocket...");
                    reconnectAttempts = 0;
                    connectChatSocket();
                } else if (chatSocket.readyState === WebSocket.OPEN) {
                    console.log("面板打開，WebSocket 已連接，啟用輸入。");
                    if (chatMessageInput) chatMessageInput.disabled = false;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = false;
                } else if (chatSocket.readyState === WebSocket.CONNECTING) {
                     console.log("面板打開，WebSocket 正在連接中...");
                     if (chatMessageInput) chatMessageInput.disabled = true; // 保持禁用直到連接成功
                     if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                }
            } else {
                 console.log("Chat panel 關閉。");
                 // 可選：關閉面板時斷開連接
                 // if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                 //     console.log("因面板關閉而關閉 WebSocket 連接。");
                 //     chatSocket.close(1000, "Panel Closed");
                 // }
            }
        });
    } else {
         console.warn("未找到聊天切換按鈕元素 (#chat-toggle-button)。");
    }


    if (chatCloseButton) {
        chatCloseButton.addEventListener('click', () => {
            isChatOpen = false;
            if (chatPanel) {
                chatPanel.classList.remove('open');
                 console.log("通過面板內按鈕關閉了聊天面板。");
                 // 可選：關閉面板時斷開連接
                 // if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                 //     console.log("因面板關閉而關閉 WebSocket 連接。");
                 //     chatSocket.close(1000, "Panel Closed");
                 // }
            }
        });
    }

    if (chatMessageSubmit) {
        chatMessageSubmit.addEventListener('click', sendMessage);
    } else {
         console.warn("未找到聊天發送按鈕元素 (#chat-message-submit)。");
    }

    if (chatMessageInput) {
        chatMessageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // 阻止默認換行
                sendMessage();     // 發送訊息
            }
        });
    } else {
         console.warn("未找到聊天訊息輸入框元素 (#chat-message-input)。");
    }

    console.log("聊天室腳本 (chat.js) 已初始化。"); // 確認腳本執行到末尾

// 確保 DOMContentLoaded 的括號是閉合的
}); // <<--- 這是檔案的最後一行，對應 document.addEventListener('DOMContentLoaded', function() {