// D:\bkgg\mybackend\chat\static\chat\js\chat.js (V8 - Inline Reply Button)

// 使用 IIFE (立即執行函數表達式) 避免污染全局作用域
(function() {
    // 在 DOM 完全加載後執行所有操作
    document.addEventListener('DOMContentLoaded', function() {
        console.log("[Chat] DOMContentLoaded 事件觸發 (V8 - Inline Reply Button)。");

        // 延遲執行
        setTimeout(() => {
            console.log("[Chat] 延遲 150ms 後開始執行聊天腳本核心邏輯。");

            if (typeof USER_ID === 'undefined' || USER_ID === null) {
                console.log("[Chat] 用戶未登入 (檢查於 setTimeout)，聊天功能已禁用。");
                return;
            }
            console.log(`[Chat] 用戶已登入 (USER_ID: ${USER_ID})，繼續初始化聊天功能...`);

            // --- DOM 元素引用 ---
            const chatModal = document.getElementById('chatModal');
            const chatMessages = document.getElementById('chat-messages');
            const chatMessageInput = document.getElementById('chat-message-input');
            const chatMessageSubmit = document.getElementById('chat-message-submit');
            const chatUnreadIndicator = document.getElementById('chat-unread-indicator');
            const replyQuoteDisplay = document.getElementById('reply-quote-display');
            const replyQuoteContent = replyQuoteDisplay?.querySelector('.reply-quote-content');
            const cancelReplyBtn = document.getElementById('cancel-reply-btn');
            // --- 移除：內容選單元素 ---
            // const chatContextMenu = document.getElementById('chat-context-menu');
            // ------------------------

            // 檢查核心元素
            let elementsFound = true;
            if (!chatModal) { console.error("[Chat] 致命錯誤：未找到聊天 Modal 容器元素 (#chatModal)。"); elementsFound = false; }
            if (!chatMessages) { console.error("[Chat] 致命錯誤：未找到聊天訊息顯示區域元素 (#chat-messages)。"); elementsFound = false; }
            if (!chatMessageInput) { console.error("[Chat] 致命錯誤：未找到聊天訊息輸入框元素 (#chat-message-input)。"); elementsFound = false; }
            if (!chatMessageSubmit) { console.error("[Chat] 致命錯誤：未找到聊天發送按鈕元素 (#chat-message-submit)。"); elementsFound = false; }
            if (!chatUnreadIndicator) { console.warn("[Chat] 警告：未找到聊天未讀標記元素 (#chat-unread-indicator)。"); }
            if (!replyQuoteDisplay) { console.warn("[Chat] 警告：未找到引用預覽顯示區域元素 (#reply-quote-display)。"); }
            if (!cancelReplyBtn) { console.warn("[Chat] 警告：未找到取消引用按鈕元素 (#cancel-reply-btn)。"); }
            // --- 移除：檢查內容選單元素 ---
            // if (!chatContextMenu) { ... }
            // -----------------------------

            if (!elementsFound) {
                console.error("[Chat] 因缺少核心元素，聊天功能無法啟動。");
                return; // 停止執行
            }
            console.log("[Chat] 所有必要的聊天 UI 元素已找到。");

            // --- 狀態變數 ---
            let chatSocket = null;
            let hasUnread = false;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5;
            const reconnectDelay = 5000;
            let initialConnectionAttempted = false;
            let currentReplyTo = null; // 儲存 { messageId: id, username: name, text: snippet }

            // --- 輔助函數 ---
            function formatTimestamp(isoTimestamp) {
                 try { if (!isoTimestamp) return ''; const date = new Date(isoTimestamp); if (isNaN(date.getTime())) { console.warn("[Chat] 無效時間戳:", isoTimestamp); return ''; } return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }); } catch (e) { console.error("[Chat] 格式化時間戳時出錯:", e, "輸入:", isoTimestamp); return ''; }
            }

            function scrollToBottom() {
                if (chatMessages) { requestAnimationFrame(() => { try { chatMessages.scrollTop = chatMessages.scrollHeight; } catch (e) { console.error("[Chat] 滾動聊天窗口錯誤:", e); } }); }
            }

            function clearReplyState() {
                currentReplyTo = null;
                if (replyQuoteDisplay) {
                    replyQuoteDisplay.style.display = 'none';
                    if(replyQuoteContent) {
                        const userStrong = replyQuoteContent.querySelector('.reply-quote-user');
                        const textSpan = replyQuoteContent.querySelector('.reply-quote-text');
                        if (userStrong) userStrong.textContent = '';
                        if (textSpan) textSpan.textContent = '';
                    }
                }
                console.log('[Chat] Reply state cleared.');
            }

            // --- 移除：隱藏內容選單 ---
            // function hideContextMenu() { ... }
            // -----------------------

            // --- 移除：顯示內容選單 ---
            // function showContextMenu(event, messageElement) { ... }
            // -----------------------

            /**
             * 將一條訊息添加到聊天顯示區域。
             * @param {object} data - 包含訊息內容的物件。
             */
            function addChatMessage(data) {
                 if (!chatMessages) { return; }
                 if (!data || typeof data !== 'object' || !data.type || data.message === undefined || (data.type === 'user' && data.message_id === undefined)) { console.warn("[Chat] 收到了無效訊息數據 (缺少 type, message 或 message_id):", data); return; }

                const messageElement = document.createElement('div');
                messageElement.classList.add('chat-message');
                if (data.message_id) {
                    messageElement.dataset.messageId = data.message_id;
                }
                const messageTime = formatTimestamp(data.timestamp || new Date().toISOString());
                const messageText = String(data.message ?? '');

                let isMine = false;

                if (data.type === 'system') {
                    messageElement.classList.add('system');
                    messageElement.textContent = `[${messageTime}] ${messageText}`;
                    messageElement.style.cursor = 'default';
                } else if (data.type === 'user') {
                    if (data.user_id === undefined || data.username === undefined) {
                        console.warn("[Chat] 用戶訊息缺少 user_id 或 username:", data);
                        return;
                    }
                    messageElement.classList.add('user');
                    // messageElement.style.cursor = 'pointer'; // 不再需要點擊整個氣泡

                    const currentUserId = typeof USER_ID === 'string' ? parseInt(USER_ID, 10) : USER_ID;
                    const messageUserId = typeof data.user_id === 'string' ? parseInt(data.user_id, 10) : data.user_id;

                    if (isNaN(currentUserId) || isNaN(messageUserId)) {
                         console.error("[Chat] 無法比較 User ID，類型或值無效。", `Current: ${USER_ID}`, `Message: ${data.user_id}`);
                    } else {
                       isMine = (messageUserId === currentUserId);
                       if (isMine) { messageElement.classList.add('mine'); }
                    }

                    // --- 處理引用預覽 (保持不變) ---
                    if (data.reply_to_id && data.quoted_username && data.quoted_message_text) {
                        const quotePreview = document.createElement('div');
                        quotePreview.classList.add('quoted-message-preview');
                        quotePreview.dataset.replyToId = data.reply_to_id;
                        quotePreview.innerHTML = `
                            <span class="quoted-user">${data.quoted_username}</span>
                            <span class="quoted-text">${data.quoted_message_text}</span>
                        `;
                        quotePreview.addEventListener('click', (e) => {
                           e.stopPropagation(); // 阻止點擊引用塊觸發父訊息的其他事件
                           console.log(`Clicked quote preview for message ID: ${data.reply_to_id}`);
                           const originalMessageElement = chatMessages.querySelector(`.chat-message[data-message-id="${data.reply_to_id}"]`);
                           if (originalMessageElement) {
                               originalMessageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                               originalMessageElement.style.transition = 'background-color 0.5s ease';
                               originalMessageElement.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                               setTimeout(() => { originalMessageElement.style.backgroundColor = ''; }, 1500);
                           } else {
                               console.warn(`Original message element with ID ${data.reply_to_id} not found in current view.`);
                           }
                        });
                        messageElement.appendChild(quotePreview);
                    }
                    // ---------------------

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

                    // --- **新增**添加回覆按鈕 ---
                    const replyButton = document.createElement('button');
                    replyButton.className = 'reply-trigger-btn'; // 使用新 class
                    replyButton.title = '回覆';
                    replyButton.setAttribute('aria-label', '回覆此訊息');
                    replyButton.dataset.messageId = data.message_id;
                    replyButton.dataset.username = String(data.username || '匿名');
                    // 預先生成預覽文本片段
                    const snippet = messageText.length > 25 ? messageText.substring(0, 25) + '...' : messageText;
                    replyButton.dataset.textSnippet = snippet;
                    replyButton.innerHTML = '<i class="fas fa-reply"></i>'; // FontAwesome 圖標
                    messageElement.appendChild(replyButton);
                    // ----------------------------

                } else {
                    console.warn("[Chat] 未知訊息類型:", data.type, data);
                    return;
                }

                // ... (添加到 DOM 和處理未讀標記的邏輯保持不變) ...
                try {
                    const initialMessage = chatMessages.querySelector('.chat-message.system:only-child');
                    if (initialMessage && (initialMessage.textContent.includes('連接中') || initialMessage.textContent.includes('載入最近訊息') || initialMessage.textContent.includes('訊息結束'))) {
                         if (data.type === 'user' || (data.type === 'system' && !initialMessage.textContent.includes(data.message))) {
                              chatMessages.innerHTML = '';
                         }
                    }
                    if (data.type === 'system' && chatMessages.lastElementChild && chatMessages.lastElementChild.classList.contains('system') && chatMessages.lastElementChild.textContent.includes(messageText)) {
                       console.log('[Chat] Skipping duplicate system message:', messageText);
                    } else {
                       chatMessages.appendChild(messageElement);
                    }

                    if (data.type !== 'system' || messageText === '--- 訊息結束 ---') {
                       scrollToBottom();
                    }
                } catch (e) {
                    console.error("[Chat] 添加訊息到 DOM 錯誤:", e);
                }

                if (chatUnreadIndicator) {
                    const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                    if (!isChatVisible && data.type === 'user' && !isMine) {
                        if (!hasUnread) { console.log("[Chat] 收到新訊息，聊天 Modal 不可見，標記為未讀。"); }
                        hasUnread = true;
                        chatUnreadIndicator.style.display = 'block';
                    }
                }
            }


            function sendMessage() {
                 if (!chatMessageInput) return;
                 if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) { console.error("[Chat] 無法發送：WebSocket 未連接。"); addChatMessage({ type: 'system', message: '錯誤：連接已斷開。', timestamp: new Date().toISOString() }); return; }
                 const message = chatMessageInput.value.trim();
                 if (message) {
                    console.log('[Chat] 發送訊息:', message);
                    try {
                        const payload = { 'message': message };
                        if (currentReplyTo && currentReplyTo.messageId) {
                            payload['reply_to_id'] = currentReplyTo.messageId;
                            console.log(`[Chat] Sending message with reply_to_id: ${currentReplyTo.messageId}`);
                        }
                        chatSocket.send(JSON.stringify(payload));
                        chatMessageInput.value = '';
                        clearReplyState(); // 發送成功後清理引用
                    } catch (error) {
                        console.error("[Chat] 發送訊息錯誤:", error);
                        addChatMessage({ type: 'system', message: `發送失敗: ${error.message}`, timestamp: new Date().toISOString() });
                    }
                 }
                 chatMessageInput.focus();
            }

            function connectChatSocket() {
                if (chatSocket && (chatSocket.readyState === WebSocket.CONNECTING || chatSocket.readyState === WebSocket.OPEN)) { console.log("[Chat] 跳過連接：已有連接。"); return; }
                if (chatSocket) { console.log("[Chat] 清理舊 WebSocket..."); chatSocket.onopen = chatSocket.onmessage = chatSocket.onclose = chatSocket.onerror = null; try { if (chatSocket.readyState !== WebSocket.CLOSED) { chatSocket.close(); } } catch (e) {} chatSocket = null; }

                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'; const wsPath = `/ws/chat/`; const wsURL = `${wsProtocol}//${window.location.host}${wsPath}`;
                console.log(`[Chat] 嘗試連接: ${wsURL} (第 ${reconnectAttempts + 1} 次)`);
                if (chatMessages) { chatMessages.innerHTML = '<div class="chat-message system">連接中...</div>'; }
                clearReplyState();
                if (chatMessageInput) chatMessageInput.disabled = true; if (chatMessageSubmit) chatMessageSubmit.disabled = true;

                try { chatSocket = new WebSocket(wsURL); } catch (error) { console.error("[Chat] 創建 WebSocket 失敗:", error); handleConnectionError("創建 WebSocket 失敗"); if (reconnectAttempts < maxReconnectAttempts) { reconnectAttempts++; setTimeout(connectChatSocket, reconnectDelay); } return; }

                chatSocket.onopen = function(e) {
                    console.log('[Chat] WebSocket 連接成功。');
                    reconnectAttempts = 0;
                    if (chatMessageInput) chatMessageInput.disabled = false;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = false;
                    if (hasUnread && chatUnreadIndicator) {
                        const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                        if (isChatVisible) { hasUnread = false; chatUnreadIndicator.style.display = 'none'; }
                    }
                    const isChatVisibleOnOpen = chatModal && window.getComputedStyle(chatModal).display === 'block';
                    if (isChatVisibleOnOpen && chatMessageInput) { setTimeout(() => chatMessageInput.focus(), 50); }
                    // Request recent messages after connection opens
                     try {
                        console.log("[Chat] Requesting recent messages...");
                        chatSocket.send(JSON.stringify({ type: 'request_recent_messages' }));
                     } catch (err) {
                        console.error("[Chat] Error requesting recent messages:", err);
                     }
                };

                chatSocket.onmessage = function(e) {
                    try {
                        const data = JSON.parse(e.data);
                        // Check for message history type
                        if (data.type === 'message_history') {
                             console.log(`[Chat] Received message history (${data.messages.length} messages).`);
                             // Clear 'Connecting...' or 'Loading...' message only if history is received
                             if (chatMessages.children.length === 1 && chatMessages.firstElementChild.classList.contains('system')) {
                                chatMessages.innerHTML = ''; // Clear loading message
                             }
                             if (data.messages && data.messages.length > 0) {
                                data.messages.forEach(msg => addChatMessage(msg));
                                addChatMessage({ type: 'system', message: '--- 訊息結束 ---', timestamp: new Date().toISOString() });
                             } else {
                                addChatMessage({ type: 'system', message: '沒有歷史訊息。', timestamp: new Date().toISOString() });
                             }
                             scrollToBottom(); // Scroll after history is loaded
                        } else {
                            addChatMessage(data); // Handle regular messages
                        }
                    } catch (error) {
                        console.error("[Chat] 解析訊息錯誤:", error, "Data:", e.data);
                         addChatMessage({ type: 'system', message: '收到格式錯誤的訊息。', timestamp: new Date().toISOString() });
                    }
                };

                chatSocket.onclose = function(e) {
                    console.error('[Chat] WebSocket 連接關閉。 Code:', e.code, 'Reason:', e.reason || '(無)', 'Clean:', e.wasClean);
                    if (chatMessageInput) chatMessageInput.disabled = true; if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                    clearReplyState();
                    const wasConnected = chatSocket === this; if (wasConnected) chatSocket = null;
                    const normalCloseCodes = [1000, 1001, 1005];
                    if (!normalCloseCodes.includes(e.code) && reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++; console.log(`[Chat] ${reconnectDelay / 1000} 秒後重連 (嘗試 ${reconnectAttempts}/${maxReconnectAttempts})`);
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
                     clearReplyState();
                     if (chatMessages) addChatMessage({ type: 'system', message: '發生連接錯誤。', timestamp: new Date().toISOString() });
                     // Optionally trigger reconnect on error as well, if not already handled by onclose
                     // if (!chatSocket || chatSocket.readyState === WebSocket.CLOSED) {
                     //    if (reconnectAttempts < maxReconnectAttempts) { ... setTimeout(connectChatSocket, reconnectDelay); }
                     //}
                };
            }

            function handleConnectionError(errorMessage = "連接錯誤") {
                 console.error(`[Chat] 處理連接錯誤: ${errorMessage}`);
                 clearReplyState();
                 if (chatMessageInput) chatMessageInput.disabled = true; if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                 if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED && chatSocket.readyState !== WebSocket.CLOSING) { console.log("[Chat] 嘗試關閉錯誤狀態的 WebSocket..."); chatSocket.onerror = chatSocket.onclose = null; try { chatSocket.close(1011, "Client-side error"); } catch (e) {} }
                 chatSocket = null; if (chatMessages) addChatMessage({ type: 'system', message: `連接失敗: ${errorMessage}。`, timestamp: new Date().toISOString() });
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
                 chatMessageInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape' && currentReplyTo) {
                        e.preventDefault();
                        clearReplyState();
                    }
                 });
            }
            if (cancelReplyBtn) {
                cancelReplyBtn.addEventListener('click', clearReplyState);
            }

            // --- **修改：為聊天訊息容器添加點擊事件監聽 (事件委派)** ---
            if (chatMessages) {
                chatMessages.addEventListener('click', function(event) {
                    // 1. 檢查是否點擊了回覆按鈕
                    const replyButton = event.target.closest('.reply-trigger-btn');
                    if (replyButton) {
                        event.stopPropagation(); // 阻止事件冒泡

                        const messageId = replyButton.dataset.messageId;
                        const username = replyButton.dataset.username;
                        const snippet = replyButton.dataset.textSnippet;

                        if (messageId && username && snippet !== undefined) { // 確保 snippet 存在
                            console.log(`[Chat] Reply button clicked for message ID: ${messageId}`);
                            // 直接設置回覆狀態
                            currentReplyTo = {
                                messageId: messageId,
                                username: username,
                                text: snippet // 使用預先生成的 snippet
                            };
                            // 更新引用預覽顯示區域
                            if (replyQuoteDisplay && replyQuoteContent) {
                                const userStrong = replyQuoteContent.querySelector('.reply-quote-user');
                                const textSpan = replyQuoteContent.querySelector('.reply-quote-text');
                                if(userStrong) userStrong.textContent = username;
                                if(textSpan) textSpan.textContent = snippet;
                                replyQuoteDisplay.style.display = 'flex'; // 顯示預覽
                            }
                            if (chatMessageInput) chatMessageInput.focus(); // 聚焦輸入框
                        } else {
                            console.warn('[Chat] Reply button missing required data attributes (messageId, username, textSnippet).', replyButton.dataset);
                        }
                        return; // 處理完畢，不再執行後續檢查
                    }

                    // 2. 檢查是否點擊了引用預覽區塊 (保持不變)
                    const quotePreview = event.target.closest('.quoted-message-preview');
                    if (quotePreview) {
                        event.stopPropagation();
                        const replyToId = quotePreview.dataset.replyToId;
                        console.log(`Clicked quote preview for message ID: ${replyToId}`);
                        const originalMessageElement = chatMessages.querySelector(`.chat-message[data-message-id="${replyToId}"]`);
                        if (originalMessageElement) {
                            originalMessageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            originalMessageElement.style.transition = 'background-color 0.5s ease';
                            originalMessageElement.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                            setTimeout(() => { originalMessageElement.style.backgroundColor = ''; }, 1500);
                        } else {
                            console.warn(`Original message element with ID ${replyToId} not found.`);
                        }
                        return; // 處理完畢
                    }

                    // --- 移除：處理點擊訊息本身觸發選單的邏輯 ---
                    // const messageElement = event.target.closest('.chat-message.user[data-message-id]');
                    // if (messageElement) { ... showContextMenu ... }
                    // else { hideContextMenu(); }
                    // ------------------------------------------
                });
            }
            // ----------------------------------------------------

            // --- 移除：為內容選單添加點擊事件監聽 ---
            // if (chatContextMenu) { chatContextMenu.addEventListener('click', ...); }
            // ----------------------------------------------------

            // --- 移除：全局點擊和 ESC 監聽器 (用於關閉選單) ---
            // document.addEventListener('click', function(event) { ... });
            // document.addEventListener('keydown', function(event) { ... });
            // ----------------------------------------------------


            // --- MutationObserver for Modal Visibility (保持不變) ---
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
                        if (!isChatVisible) {
                             clearReplyState(); // 關閉 Modal 時取消引用
                             // hideContextMenu(); // 不再需要
                        }
                        if (isChatVisible && (!chatSocket || chatSocket.readyState === WebSocket.CLOSED || chatSocket.readyState === WebSocket.CLOSING)) {
                             console.log("[Chat] 聊天 Modal 打開，但 WebSocket 未連接或已關閉，嘗試重新連接...");
                             reconnectAttempts = 0;
                             connectChatSocket();
                        } else if (isChatVisible && chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                            scrollToBottom();
                            setTimeout(() => { if (chatMessageInput) chatMessageInput.focus(); }, 100);
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

            console.log("[Chat] 聊天室腳本核心邏輯初始化完畢 (V8 - Inline Reply Button)。");

        }, 150); // 保持延遲

    }); // DOMContentLoaded 結束
})(); // IIFE 結束