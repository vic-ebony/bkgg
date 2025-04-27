// --- START OF COMPLETE chat.js ---
// D:\bkgg\mybackend\chat\static\chat\js\chat.js (V5 修復 isMine 錯誤)

// 使用 IIFE (立即執行函數表達式) 避免污染全局作用域
(function() {
    // 在 DOM 完全加載後執行所有操作
    document.addEventListener('DOMContentLoaded', function() {
        console.log("[Chat] DOMContentLoaded 事件觸發。");

        // 延遲執行，確保 DOM 完全準備好，特別是異步加載或複雜渲染後
        setTimeout(() => {
            console.log("[Chat] 延遲 150ms 後開始執行聊天腳本核心邏輯。");

            // 再次檢查用戶是否登入
            if (typeof USER_ID === 'undefined' || USER_ID === null) {
                console.log("[Chat] 用戶未登入 (檢查於 setTimeout)，聊天功能已禁用。");
                return;
            }
            console.log(`[Chat] 用戶已登入 (USER_ID: ${USER_ID})，繼續初始化聊天功能...`);

            // --- DOM 元素引用 (在延遲後獲取) ---
            const chatModal = document.getElementById('chatModal');
            const chatMessages = document.getElementById('chat-messages');
            const chatMessageInput = document.getElementById('chat-message-input');
            const chatMessageSubmit = document.getElementById('chat-message-submit');
            const chatUnreadIndicator = document.getElementById('chat-unread-indicator');

            // 檢查核心元素是否存在
            let elementsFound = true;
            if (!chatModal) {
                console.error("[Chat] 致命錯誤：未找到聊天 Modal 容器元素 (#chatModal)。請仔細檢查 index.html 是否正確渲染此元素。");
                elementsFound = false;
            }
            if (!chatMessages) {
                console.error("[Chat] 致命錯誤：未找到聊天訊息顯示區域元素 (#chat-messages)。");
                elementsFound = false;
            }
            if (!chatMessageInput) {
                console.error("[Chat] 致命錯誤：未找到聊天訊息輸入框元素 (#chat-message-input)。");
                elementsFound = false;
            }
            if (!chatMessageSubmit) {
                console.error("[Chat] 致命錯誤：未找到聊天發送按鈕元素 (#chat-message-submit)。");
                elementsFound = false;
            }
            if (!chatUnreadIndicator) {
                console.warn("[Chat] 警告：未找到聊天未讀標記元素 (#chat-unread-indicator)。");
            }

            if (!elementsFound) {
                console.error("[Chat] 因缺少核心元素，聊天功能無法啟動。");
                return; // 停止執行
            }
            console.log("[Chat] 所有必要的聊天 UI 元素已找到。");

            // --- 狀態變數 ---
            let chatSocket = null;       // WebSocket 實例
            let hasUnread = false;       // 是否有未讀消息
            let reconnectAttempts = 0;   // 當前重連次數
            const maxReconnectAttempts = 5; // 最大重連次數
            const reconnectDelay = 5000; // 重連延遲 (毫秒)
            let initialConnectionAttempted = false; // 標記是否已嘗試過初始連接

            // --- 輔助函數 ---
            function formatTimestamp(isoTimestamp) {
                try {
                    if (!isoTimestamp) return '';
                    const date = new Date(isoTimestamp);
                    if (isNaN(date.getTime())) {
                        console.warn("[Chat] 無效時間戳:", isoTimestamp);
                        return '';
                    }
                    return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
                } catch (e) {
                    console.error("[Chat] 格式化時間戳時出錯:", e, "輸入:", isoTimestamp);
                    return '';
                }
            }

            function scrollToBottom() {
                if (chatMessages) {
                    requestAnimationFrame(() => {
                        try {
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        } catch (e) {
                            console.error("[Chat] 滾動聊天窗口錯誤:", e);
                        }
                    });
                }
            }

            /**
             * 將一條訊息添加到聊天顯示區域。
             * @param {object} data - 包含訊息內容的物件。
             */
            function addChatMessage(data) {
                if (!chatMessages) { return; }
                if (!data || typeof data !== 'object' || !data.type || data.message === undefined) {
                    console.warn("[Chat] 收到了無效訊息數據:", data);
                    return;
                }

                const messageElement = document.createElement('div');
                messageElement.classList.add('chat-message');
                const messageTime = formatTimestamp(data.timestamp || new Date().toISOString());
                const messageText = String(data.message ?? ''); // 確保 message 是字符串

                let isMine = false; // 預設不是自己的消息

                if (data.type === 'system') {
                    messageElement.classList.add('system');
                    messageElement.textContent = `[${messageTime}] ${messageText}`;
                } else if (data.type === 'user') {
                    if (data.user_id === undefined || data.username === undefined) {
                        console.warn("[Chat] 用戶訊息缺少 user_id 或 username:", data);
                        return;
                    }
                    messageElement.classList.add('user');
                    const currentUserId = typeof USER_ID === 'string' ? parseInt(USER_ID, 10) : USER_ID;
                    const messageUserId = typeof data.user_id === 'string' ? parseInt(data.user_id, 10) : data.user_id;
                    if (isNaN(currentUserId) || isNaN(messageUserId)) {
                         console.error("[Chat] 無法比較 User ID，類型錯誤。");
                         return;
                    }
                    isMine = (messageUserId === currentUserId); // 計算 isMine
                    if (isMine) { messageElement.classList.add('mine'); }

                    const usernameSpan = document.createElement('span');
                    usernameSpan.className = 'chat-message-header';
                    usernameSpan.textContent = String(data.username || '匿名');
                    messageElement.appendChild(usernameSpan);

                    const messageSpan = document.createElement('span');
                    messageSpan.textContent = messageText;
                    messageElement.appendChild(messageSpan);

                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'chat-message-time';
                    timeSpan.textContent = messageTime;
                    messageElement.appendChild(timeSpan);
                } else {
                    console.warn("[Chat] 未知訊息類型:", data.type, data);
                    return;
                }

                try {
                    chatMessages.appendChild(messageElement);
                    scrollToBottom();
                } catch (e) {
                    console.error("[Chat] 添加訊息到 DOM 錯誤:", e);
                }

                // 更新未讀標記 (檢查 Modal 是否可見 以及 是否非自己的消息)
                if (chatUnreadIndicator) {
                    const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                    // *** 修正：只有當 Modal 不可見 且 消息不是自己的 才標記未讀 ***
                    if (!isChatVisible && data.type === 'user' && !isMine) {
                        if (!hasUnread) { console.log("[Chat] 收到新訊息，聊天 Modal 不可見，標記為未讀。"); }
                        hasUnread = true;
                        chatUnreadIndicator.style.display = 'block';
                    }
                }
            }


            function sendMessage() {
                if (!chatMessageInput) return;
                 if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
                    console.error("[Chat] 無法發送：WebSocket 未連接。");
                    addChatMessage({ type: 'system', message: '錯誤：連接已斷開。', timestamp: new Date().toISOString() });
                    return;
                }
                const message = chatMessageInput.value.trim();
                if (message) {
                    console.log('[Chat] 發送訊息:', message);
                    try {
                        chatSocket.send(JSON.stringify({ 'message': message }));
                        chatMessageInput.value = '';
                    } catch (error) {
                        console.error("[Chat] 發送訊息錯誤:", error);
                        addChatMessage({ type: 'system', message: `發送失敗: ${error.message}`, timestamp: new Date().toISOString() });
                    }
                }
                chatMessageInput.focus();
            }

            function connectChatSocket() {
                if (chatSocket && (chatSocket.readyState === WebSocket.CONNECTING || chatSocket.readyState === WebSocket.OPEN)) {
                    console.log("[Chat] 跳過連接：已有連接。");
                    return;
                }
                if (chatSocket) {
                     console.log("[Chat] 清理舊 WebSocket...");
                     chatSocket.onopen = chatSocket.onmessage = chatSocket.onclose = chatSocket.onerror = null;
                     try { if (chatSocket.readyState !== WebSocket.CLOSED) { chatSocket.close(); } } catch (e) {}
                     chatSocket = null;
                }

                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsPath = `/ws/chat/`;
                const wsURL = `${wsProtocol}//${window.location.host}${wsPath}`;

                console.log(`[Chat] 嘗試連接: ${wsURL} (第 ${reconnectAttempts + 1} 次)`);
                if (chatMessages) { addChatMessage({ type: 'system', message: `正在連接聊天室... (嘗試 ${reconnectAttempts + 1})`, timestamp: new Date().toISOString() }); }
                if (chatMessageInput) chatMessageInput.disabled = true;
                if (chatMessageSubmit) chatMessageSubmit.disabled = true;

                try {
                    chatSocket = new WebSocket(wsURL);
                } catch (error) {
                    console.error("[Chat] 創建 WebSocket 失敗:", error);
                    handleConnectionError("創建 WebSocket 失敗");
                    if (reconnectAttempts < maxReconnectAttempts) { reconnectAttempts++; setTimeout(connectChatSocket, reconnectDelay); }
                    return;
                }

                chatSocket.onopen = function(e) {
                    console.log('[Chat] WebSocket 連接成功。');
                    reconnectAttempts = 0;
                    if (chatMessageInput) chatMessageInput.disabled = false;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = false;
                    addChatMessage({ type: 'system', message: '已連接。', timestamp: new Date().toISOString() });
                    if (hasUnread && chatUnreadIndicator) {
                        // 檢查 Modal 是否可見，如果不可見則不清空未讀（可能後台連接成功）
                        const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                        if (isChatVisible) {
                             hasUnread = false;
                             chatUnreadIndicator.style.display = 'none';
                        }
                    }
                    scrollToBottom();
                    // 聚焦輸入框（如果Modal可見）
                     const isChatVisibleOnOpen = chatModal && window.getComputedStyle(chatModal).display === 'block';
                     if (isChatVisibleOnOpen && chatMessageInput) {
                         chatMessageInput.focus();
                     }
                };

                chatSocket.onmessage = function(e) {
                    try {
                        const data = JSON.parse(e.data);
                        addChatMessage(data);
                    } catch (error) {
                        console.error("[Chat] 解析訊息錯誤:", error, "Data:", e.data);
                         addChatMessage({ type: 'system', message: '收到格式錯誤的訊息。', timestamp: new Date().toISOString() });
                    }
                };

                chatSocket.onclose = function(e) {
                    console.error('[Chat] WebSocket 連接關閉。 Code:', e.code, 'Reason:', e.reason || '(無)', 'Clean:', e.wasClean);
                    if (chatMessageInput) chatMessageInput.disabled = true;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                    const wasConnected = chatSocket === this;
                    if (wasConnected) chatSocket = null;
                    const normalCloseCodes = [1000, 1001, 1005];
                    if (!normalCloseCodes.includes(e.code) && reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log(`[Chat] ${reconnectDelay / 1000} 秒後重連 (嘗試 ${reconnectAttempts}/${maxReconnectAttempts})`);
                        if (chatMessages) addChatMessage({ type: 'system', message: `連接斷開，${reconnectDelay / 1000}秒後重連...`, timestamp: new Date().toISOString() });
                        setTimeout(connectChatSocket, reconnectDelay);
                    } else if (normalCloseCodes.includes(e.code)) {
                         if (chatMessages) addChatMessage({ type: 'system', message: '連接已關閉。', timestamp: new Date().toISOString() });
                    } else {
                         if (chatMessages) addChatMessage({ type: 'system', message: '重連失敗。請刷新頁面重試。', timestamp: new Date().toISOString() });
                    }
                };

                chatSocket.onerror = function(err) {
                    console.error('[Chat] WebSocket 錯誤:', err);
                     if (chatMessages) addChatMessage({ type: 'system', message: '發生連接錯誤。', timestamp: new Date().toISOString() });
                };
            }

            function handleConnectionError(errorMessage = "連接錯誤") {
                 console.error(`[Chat] 處理連接錯誤: ${errorMessage}`);
                 if (chatMessageInput) chatMessageInput.disabled = true;
                 if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                 if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED && chatSocket.readyState !== WebSocket.CLOSING) {
                    console.log("[Chat] 嘗試關閉錯誤狀態的 WebSocket...");
                    chatSocket.onerror = chatSocket.onclose = null;
                    try { chatSocket.close(1011, "Client-side error"); } catch (e) {}
                 }
                 chatSocket = null;
                 if (chatMessages) addChatMessage({ type: 'system', message: `連接失敗: ${errorMessage}。`, timestamp: new Date().toISOString() });
            }

            // --- UI 事件監聽器設定 ---
            if (chatMessageSubmit) {
                chatMessageSubmit.addEventListener('click', sendMessage);
            }
            if (chatMessageInput) {
                chatMessageInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey && chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                        e.preventDefault();
                        sendMessage();
                    }
                });
            }

            // --- MutationObserver for Modal Visibility ---
            const chatModalObserver = new MutationObserver((mutationsList) => {
                for(let mutation of mutationsList) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                        const displayStyle = window.getComputedStyle(chatModal).display;
                        const isChatVisible = displayStyle === 'block';
                        if (isChatVisible && hasUnread) {
                            console.log("[Chat] 聊天 Modal 變為可見，清除未讀標記。");
                            hasUnread = false;
                            if (chatUnreadIndicator) { chatUnreadIndicator.style.display = 'none'; }
                            scrollToBottom();
                            setTimeout(() => { if (chatMessageInput) chatMessageInput.focus(); }, 100);
                        }
                        // 當 Modal 打開時，確保連接是正常的，如果不是則嘗試連接
                        if (isChatVisible && (!chatSocket || chatSocket.readyState === WebSocket.CLOSED)) {
                             console.log("[Chat] 聊天 Modal 打開，但 WebSocket 未連接或已關閉，嘗試重新連接...");
                             reconnectAttempts = 0; // 重置重連次數
                             connectChatSocket();
                        }
                    }
                }
            });
            if (chatModal) {
                chatModalObserver.observe(chatModal, { attributes: true, attributeFilter: ['style'] });
            }

            // --- 初始連接 ---
            if (!initialConnectionAttempted) {
                 console.log("[Chat] 嘗試初始 WebSocket 連接...");
                 connectChatSocket();
                 initialConnectionAttempted = true;
            }

            console.log("[Chat] 聊天室腳本核心邏輯初始化完畢。");

        }, 150); // 保持延遲

    }); // DOMContentLoaded 結束
})(); // IIFE 結束
// --- END OF COMPLETE chat.js ---