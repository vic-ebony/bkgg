// D:\bkgg\mybackend\chat\static\chat\js\chat.js (V9 - Display User Title)

// 使用 IIFE (立即執行函數表達式) 避免污染全局作用域
(function() {
    // 在 DOM 完全加載後執行所有操作
    document.addEventListener('DOMContentLoaded', function() {
        console.log("[Chat] DOMContentLoaded 事件觸發 (V9 - Display User Title)。");

        // 延遲執行
        setTimeout(() => {
            console.log("[Chat] 延遲 150ms 後開始執行聊天腳本核心邏輯。");

            // 檢查用戶是否登入 (USER_ID 應由主模板定義)
            if (typeof USER_ID === 'undefined' || USER_ID === null) {
                console.log("[Chat] 用戶未登入 (檢查於 setTimeout)，聊天功能已禁用。");
                // 可以考慮隱藏聊天入口按鈕等
                const chatToggleButton = document.getElementById('chat-toggle-button');
                if(chatToggleButton) chatToggleButton.style.display = 'none';
                return; // 停止初始化
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

            // 檢查核心元素
            let elementsFound = true;
            if (!chatModal) { console.error("[Chat] 致命錯誤：未找到聊天 Modal 容器元素 (#chatModal)。"); elementsFound = false; }
            if (!chatMessages) { console.error("[Chat] 致命錯誤：未找到聊天訊息顯示區域元素 (#chat-messages)。"); elementsFound = false; }
            if (!chatMessageInput) { console.error("[Chat] 致命錯誤：未找到聊天訊息輸入框元素 (#chat-message-input)。"); elementsFound = false; }
            if (!chatMessageSubmit) { console.error("[Chat] 致命錯誤：未找到聊天發送按鈕元素 (#chat-message-submit)。"); elementsFound = false; }
            if (!chatUnreadIndicator) { console.warn("[Chat] 警告：未找到聊天未讀標記元素 (#chat-unread-indicator)。"); }
            if (!replyQuoteDisplay) { console.warn("[Chat] 警告：未找到引用預覽顯示區域元素 (#reply-quote-display)。"); }
            if (!cancelReplyBtn) { console.warn("[Chat] 警告：未找到取消引用按鈕元素 (#cancel-reply-btn)。"); }

            if (!elementsFound) {
                console.error("[Chat] 因缺少核心元素，聊天功能無法啟動。");
                return; // 停止執行
            }
            console.log("[Chat] 所有必要的聊天 UI 元素已找到。");

            // --- 狀態變數 ---
            let chatSocket = null;
            let hasUnread = false;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 5; // Maximum number of reconnection attempts
            const reconnectDelay = 5000;    // Delay between attempts in milliseconds (5 seconds)
            let initialConnectionAttempted = false; // Flag to prevent multiple initial connects
            let currentReplyTo = null; // Stores { messageId: id, username: name, text: snippet } for reply

            // --- 輔助函數 ---
            /**
             * Formats an ISO timestamp string into HH:MM format.
             * @param {string} isoTimestamp - The ISO timestamp string.
             * @returns {string} Formatted time string or empty string on error.
             */
            function formatTimestamp(isoTimestamp) {
                 try {
                     if (!isoTimestamp) return '';
                     // Create Date object. Handles potential Z or +HH:MM offsets.
                     const date = new Date(isoTimestamp);
                     // Check if date is valid
                     if (isNaN(date.getTime())) {
                         console.warn("[Chat] 無效時間戳:", isoTimestamp);
                         return '';
                     }
                     // Format to HH:MM (24-hour format) using browser's locale support for time formatting
                     return date.toLocaleTimeString('en-GB', { // en-GB often gives HH:MM
                         hour: '2-digit',
                         minute: '2-digit',
                         hour12: false // Force 24-hour format
                     });
                 } catch (e) {
                     console.error("[Chat] 格式化時間戳時出錯:", e, "輸入:", isoTimestamp);
                     return ''; // Return empty string on error
                 }
            }

            /**
             * Scrolls the chat messages container to the bottom smoothly.
             */
            function scrollToBottom() {
                if (chatMessages) {
                    // Use requestAnimationFrame for smoother scrolling, especially after adding elements
                    requestAnimationFrame(() => {
                        try {
                             // Check if user is scrolled up significantly (more than 100px from bottom)
                             const isScrolledUp = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight > 100;
                             // Only scroll automatically if user isn't intentionally scrolled up
                             if (!isScrolledUp) {
                                 chatMessages.scrollTop = chatMessages.scrollHeight;
                             } else {
                                 console.log("[Chat] User scrolled up, not auto-scrolling to bottom.");
                             }
                        } catch (e) {
                            console.error("[Chat] 滾動聊天窗口錯誤:", e);
                        }
                    });
                }
            }

             /**
             * Clears the current reply state (both internal variable and UI preview).
             */
            function clearReplyState() {
                currentReplyTo = null;
                if (replyQuoteDisplay) {
                    replyQuoteDisplay.style.display = 'none'; // Hide the preview bar
                    // Clear the content inside the preview bar
                    if(replyQuoteContent) {
                        const userStrong = replyQuoteContent.querySelector('.reply-quote-user');
                        const textSpan = replyQuoteContent.querySelector('.reply-quote-text');
                        if (userStrong) userStrong.textContent = '';
                        if (textSpan) textSpan.textContent = '';
                    }
                }
                console.log('[Chat] Reply state cleared.');
            }

            /**
             * Adds a chat message to the chat display area.
             * Handles different message types (system, user) and displays user titles.
             * @param {object} data - Message data received from the WebSocket. Expected keys:
             *                        type ('system' or 'user'), message (string), [timestamp],
             *                        [message_id], [username], [user_id], [user_title],
             *                        [reply_to_id], [quoted_username], [quoted_message_text]
             */
            function addChatMessage(data) {
                 // --- Input Data Validation ---
                 if (!chatMessages) {
                     console.error("[Chat] Cannot add message: chatMessages element not found.");
                     return;
                 }
                 if (!data || typeof data !== 'object') {
                     console.warn("[Chat] Received invalid message data (not an object):", data);
                     return;
                 }
                 // Basic type and message content check
                 if (!data.type || data.message === undefined || data.message === null) {
                      console.warn("[Chat] Received invalid message data (missing type or message):", data);
                      return;
                 }
                 // Specific checks for user messages
                 if (data.type === 'user' && (data.message_id === undefined || data.user_id === undefined || data.username === undefined)) {
                      console.warn("[Chat] Received invalid 'user' message data (missing message_id, user_id, or username):", data);
                      return; // Crucial fields missing for user messages
                 }
                 // --- End Validation ---


                const messageElement = document.createElement('div');
                messageElement.classList.add('chat-message');
                // Add message ID if present (important for replies, etc.)
                if (data.message_id) {
                    messageElement.dataset.messageId = data.message_id;
                }
                // Format timestamp safely
                const messageTime = formatTimestamp(data.timestamp || new Date().toISOString()); // Use current time as fallback
                // Ensure message text is a string
                const messageText = String(data.message ?? ''); // Handle null/undefined message text

                let isMine = false; // Flag to identify if the message is from the current user

                // --- Handle System Messages ---
                if (data.type === 'system') {
                    messageElement.classList.add('system');
                    // Include timestamp for system messages for clarity
                    messageElement.textContent = `[${messageTime}] ${messageText}`;
                    messageElement.style.cursor = 'default'; // Not interactive
                }
                // --- Handle User Messages ---
                else if (data.type === 'user') {
                    messageElement.classList.add('user'); // Basic user message style

                    // Determine if the message is from the currently logged-in user
                    // Ensure USER_ID is treated as a number for comparison
                    const currentUserId = typeof USER_ID === 'string' ? parseInt(USER_ID, 10) : USER_ID;
                    const messageUserId = typeof data.user_id === 'string' ? parseInt(data.user_id, 10) : data.user_id;

                    if (isNaN(currentUserId) || isNaN(messageUserId)) {
                         console.error("[Chat] Cannot compare User IDs - invalid type or value.", `Current: ${USER_ID} (Type: ${typeof USER_ID})`, `Message: ${data.user_id} (Type: ${typeof data.user_id})`);
                    } else {
                       isMine = (messageUserId === currentUserId);
                       if (isMine) {
                           messageElement.classList.add('mine'); // Add 'mine' class for specific styling (e.g., right alignment)
                       }
                    }

                    // --- Handle Quoted Message Preview (if replying) ---
                    if (data.reply_to_id && data.quoted_username && data.quoted_message_text) {
                        const quotePreview = document.createElement('div');
                        quotePreview.classList.add('quoted-message-preview');
                        quotePreview.dataset.replyToId = data.reply_to_id; // Store the ID for potential click actions
                        // Sanitize content before inserting as HTML if needed, or use textContent
                        quotePreview.innerHTML = `
                            <span class="quoted-user">${escapeHtml(data.quoted_username)}</span>
                            <span class="quoted-text">${escapeHtml(data.quoted_message_text)}</span>
                        `;
                        // Add click listener to jump to the original message
                        quotePreview.addEventListener('click', (e) => {
                           e.stopPropagation(); // Prevent triggering actions on the parent message bubble
                           console.log(`Clicked quote preview for message ID: ${data.reply_to_id}`);
                           const originalMessageElement = chatMessages.querySelector(`.chat-message[data-message-id="${data.reply_to_id}"]`);
                           if (originalMessageElement) {
                               // Scroll to the original message
                               originalMessageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                               // Highlight the original message temporarily
                               originalMessageElement.style.transition = 'background-color 0.5s ease';
                               originalMessageElement.style.backgroundColor = 'rgba(255, 255, 0, 0.3)'; // Yellow highlight
                               setTimeout(() => { originalMessageElement.style.backgroundColor = ''; }, 1500); // Remove highlight after 1.5s
                           } else {
                               console.warn(`Original message element with ID ${data.reply_to_id} not found in current view.`);
                               // Optionally: show a notification that the message is not loaded
                           }
                        });
                        messageElement.appendChild(quotePreview); // Add preview block before the main content
                    }
                    // --- End Quoted Message Preview ---

                    // --- Create Header Container (Username + Title) ---
                    const headerContainer = document.createElement('div');
                    headerContainer.className = 'chat-message-header-container';

                    // Username Span
                    const usernameSpan = document.createElement('span');
                    usernameSpan.className = 'chat-message-header';
                    // Use username from data, provide fallback
                    usernameSpan.textContent = String(data.username || '匿名');
                    headerContainer.appendChild(usernameSpan);

                    // ** Check for and add User Title Span **
                    if (data.user_title) {
                        const titleSpan = document.createElement('span');
                        titleSpan.className = 'chat-user-title'; // Class for CSS styling
                        titleSpan.textContent = data.user_title; // Display the title
                        headerContainer.appendChild(titleSpan); // Append after username
                    }
                    // *************************************

                    messageElement.appendChild(headerContainer); // Add container to message bubble
                    // --- End Header Container ---

                    // --- Message Content Span ---
                    const messageSpan = document.createElement('span');
                     // Escape HTML in message content to prevent XSS if content can contain HTML
                    messageSpan.textContent = messageText; // Use textContent for safety
                    // If you MUST render HTML: messageSpan.innerHTML = sanitizedHtml(messageText);
                    messageElement.appendChild(messageSpan);
                    // --- End Message Content ---

                    // --- Timestamp Span ---
                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'chat-message-time'; // CSS will position this
                    timeSpan.textContent = messageTime;
                    messageElement.appendChild(timeSpan);
                    // --- End Timestamp ---

                    // --- Inline Reply Button ---
                    const replyButton = document.createElement('button');
                    replyButton.className = 'reply-trigger-btn';
                    replyButton.title = '回覆'; // Tooltip text
                    replyButton.setAttribute('aria-label', '回覆此訊息'); // Accessibility
                    // Store necessary data for the reply action on the button itself
                    if(data.message_id) replyButton.dataset.messageId = data.message_id;
                    replyButton.dataset.username = String(data.username || '匿名');
                    // Create a snippet of the message text for the reply preview
                    const snippet = messageText.length > 25 ? messageText.substring(0, 25) + '...' : messageText;
                    replyButton.dataset.textSnippet = snippet;
                    // Add FontAwesome icon
                    replyButton.innerHTML = '<i class="fas fa-reply"></i>';
                    messageElement.appendChild(replyButton); // Add button to the message bubble
                    // --- End Inline Reply Button ---

                }
                // --- Handle Unknown Message Types ---
                else {
                    console.warn("[Chat] Received message with unknown type:", data.type, data);
                    return; // Skip adding unknown types to the chat display
                }

                // --- Add the completed message element to the DOM ---
                try {
                    // Logic to clear initial "Connecting..." or "Loading..." messages
                    const initialSystemMessage = chatMessages.querySelector('.chat-message.system:only-child');
                    if (initialSystemMessage && (initialSystemMessage.textContent.includes('連接中') || initialSystemMessage.textContent.includes('載入最近訊息') || initialSystemMessage.textContent.includes('訊息結束'))) {
                         // Replace loading message only if the new message is not another system message repeating the same text
                         if (data.type === 'user' || (data.type === 'system' && !initialSystemMessage.textContent.includes(data.message))) {
                              chatMessages.innerHTML = ''; // Clear the initial message
                         }
                    }

                    // Prevent duplicate adjacent system messages (optional enhancement)
                    if (data.type === 'system' && chatMessages.lastElementChild && chatMessages.lastElementChild.classList.contains('system') && chatMessages.lastElementChild.textContent.includes(messageText)) {
                       // Example: Don't show "Connecting..." twice in a row
                       console.log('[Chat] Skipping duplicate system message:', messageText);
                    } else {
                       chatMessages.appendChild(messageElement); // Add the new message
                    }

                    // Scroll to bottom only for non-system messages or the end-of-history marker
                    // This prevents jumping when history loads
                    if (data.type !== 'system' || messageText === '--- 訊息結束 ---') {
                       scrollToBottom();
                    }
                } catch (e) {
                    console.error("[Chat] 添加訊息到 DOM 錯誤:", e);
                }

                // --- Update Unread Indicator ---
                if (chatUnreadIndicator) {
                    // Check if the chat modal is currently hidden
                    const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                    // Mark as unread only if chat is hidden, it's a user message, and not from self
                    if (!isChatVisible && data.type === 'user' && !isMine) {
                        if (!hasUnread) { console.log("[Chat] 收到新訊息，聊天 Modal 不可見，標記為未讀。"); }
                        hasUnread = true;
                        chatUnreadIndicator.style.display = 'block'; // Show the red dot
                    }
                }
                // --- End Unread Indicator ---
            } // End of addChatMessage function

            /**
             * Sends the message from the input field via the WebSocket.
             * Also includes reply_to_id if currently replying to a message.
             */
            function sendMessage() {
                 if (!chatMessageInput) {
                     console.error("[Chat] Cannot send: Input element not found.");
                     return;
                 }
                 // Check WebSocket connection state
                 if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
                     console.error("[Chat] 無法發送：WebSocket 未連接。");
                     // Display error to user in the chat window
                     addChatMessage({ type: 'system', message: '錯誤：連接已斷開，無法發送訊息。', timestamp: new Date().toISOString() });
                     // Optionally disable input/button again
                     chatMessageInput.disabled = true;
                     if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                     return;
                 }

                 const message = chatMessageInput.value.trim(); // Get and trim message

                 if (message) { // Only send if message is not empty
                    console.log('[Chat] 發送訊息:', message);
                    try {
                        const payload = { 'message': message };
                        // If currently replying, add the reply_to_id to the payload
                        if (currentReplyTo && currentReplyTo.messageId) {
                            payload['reply_to_id'] = currentReplyTo.messageId;
                            console.log(`[Chat] Sending message with reply_to_id: ${currentReplyTo.messageId}`);
                        }
                        // Send the payload as a JSON string
                        chatSocket.send(JSON.stringify(payload));

                        // Clear the input field and the reply state after sending
                        chatMessageInput.value = '';
                        clearReplyState();
                    } catch (error) {
                        console.error("[Chat] 發送訊息錯誤:", error);
                        // Display error to user
                        addChatMessage({ type: 'system', message: `發送失敗: ${error.message}`, timestamp: new Date().toISOString() });
                    }
                 } else {
                     console.log("[Chat] Empty message not sent.");
                 }
                 chatMessageInput.focus(); // Keep focus on the input field
            } // End of sendMessage function

            /**
             * Establishes the WebSocket connection. Handles setup, events, and basic reconnection logic.
             */
            function connectChatSocket() {
                // Prevent multiple simultaneous connection attempts
                if (chatSocket && (chatSocket.readyState === WebSocket.CONNECTING || chatSocket.readyState === WebSocket.OPEN)) {
                    console.log("[Chat] 跳過連接：已有連接或正在連接。");
                    return;
                }
                // Clean up any previous socket instance before creating a new one
                if (chatSocket) {
                    console.log("[Chat] 清理舊 WebSocket...");
                    chatSocket.onopen = chatSocket.onmessage = chatSocket.onclose = chatSocket.onerror = null; // Remove old listeners
                    try {
                        if (chatSocket.readyState !== WebSocket.CLOSED) {
                            chatSocket.close(); // Attempt to close gracefully
                            console.log("[Chat] Old WebSocket closed.");
                        }
                    } catch (e) {
                         console.warn("[Chat] Error closing old WebSocket:", e);
                    }
                    chatSocket = null;
                }

                // Determine WebSocket protocol (ws or wss) based on HTTP protocol
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsPath = `/ws/chat/`; // Your WebSocket endpoint path
                const wsURL = `${wsProtocol}//${window.location.host}${wsPath}`;

                console.log(`[Chat] 嘗試連接: ${wsURL} (第 ${reconnectAttempts + 1} 次 / ${maxReconnectAttempts} max)`);
                // Display connecting message and disable input
                if (chatMessages) { chatMessages.innerHTML = '<div class="chat-message system">連接中...</div>'; }
                clearReplyState(); // Clear reply state on new connection attempt
                if (chatMessageInput) chatMessageInput.disabled = true;
                if (chatMessageSubmit) chatMessageSubmit.disabled = true;

                try {
                    // Create the new WebSocket object
                    chatSocket = new WebSocket(wsURL);
                } catch (error) {
                    // Handle potential errors during WebSocket creation (e.g., security policy)
                    console.error("[Chat] 創建 WebSocket 失敗:", error);
                    handleConnectionError("創建 WebSocket 失敗"); // Use helper to handle UI/state
                    // Attempt to reconnect if within limits
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log(`[Chat] ${reconnectDelay / 1000} 秒後重連 (因創建失敗)...`);
                        setTimeout(connectChatSocket, reconnectDelay);
                    } else {
                         addChatMessage({ type: 'system', message: '無法建立連接。請刷新頁面。', timestamp: new Date().toISOString() });
                    }
                    return; // Stop execution for this attempt
                }

                // --- WebSocket Event Listeners ---

                // On Connection Open
                chatSocket.onopen = function(e) {
                    console.log('[Chat] WebSocket 連接成功。');
                    reconnectAttempts = 0; // Reset reconnection attempts on successful connection
                    // Enable input/submit buttons
                    if (chatMessageInput) chatMessageInput.disabled = false;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = false;

                    // If there were unread messages, clear the indicator if chat is now visible
                    if (hasUnread && chatUnreadIndicator) {
                        const isChatVisible = chatModal && window.getComputedStyle(chatModal).display === 'block';
                        if (isChatVisible) {
                             console.log("[Chat] Chat visible on connect, clearing unread status.");
                             hasUnread = false;
                             chatUnreadIndicator.style.display = 'none';
                        }
                    }

                    // Focus input if chat is open when connection is established
                    const isChatVisibleOnOpen = chatModal && window.getComputedStyle(chatModal).display === 'block';
                    if (isChatVisibleOnOpen && chatMessageInput) {
                         console.log("[Chat] Focusing input field after connection open.");
                         setTimeout(() => chatMessageInput.focus(), 50); // Small delay might help
                    }

                    // Request recent messages after connection is established
                    try {
                        console.log("[Chat] Requesting recent messages upon connection...");
                        chatSocket.send(JSON.stringify({ type: 'request_recent_messages' }));
                    } catch (err) {
                        console.error("[Chat] Error sending request for recent messages:", err);
                    }
                };

                // On Message Received
                chatSocket.onmessage = function(e) {
                    try {
                        const data = JSON.parse(e.data);
                        // Log received data type for debugging
                        // console.log("[Chat] Received data:", data.type, data);

                        // Handle different message types from the server
                        if (data.type === 'message_history') {
                             console.log(`[Chat] Received message history (${data.messages?.length || 0} messages).`);
                             // Clear 'Connecting...' or 'Loading...' message ONLY if history is received
                             if (chatMessages.children.length === 1 && chatMessages.firstElementChild.classList.contains('system')) {
                                chatMessages.innerHTML = ''; // Clear loading message
                             }
                             // Add historical messages (oldest first if backend reversed it)
                             if (data.messages && data.messages.length > 0) {
                                data.messages.forEach(msg => addChatMessage(msg)); // Add each historical message
                                // Add a separator after history (optional)
                                addChatMessage({ type: 'system', message: '--- 訊息結束 ---', timestamp: new Date().toISOString() });
                             } else {
                                // Indicate if no history was found
                                addChatMessage({ type: 'system', message: '沒有歷史訊息。', timestamp: new Date().toISOString() });
                             }
                             // Scroll after history is fully loaded
                             // Use setTimeout to ensure rendering is complete before scrolling
                             setTimeout(scrollToBottom, 0);
                        } else if (data.type === 'user' || data.type === 'system') {
                            // Handle regular live messages
                            addChatMessage(data);
                        } else if (data.type === 'error') { // Handle specific error messages from backend
                            console.error("[Chat] Received error message from server:", data.message);
                            addChatMessage({ type: 'system', message: `伺服器錯誤: ${data.message}`, timestamp: new Date().toISOString() });
                        } else {
                             console.warn("[Chat] Received message with unknown type:", data.type, data);
                             // Optionally display a generic system message for unknown types
                             // addChatMessage({ type: 'system', message: `收到未知訊息類型: ${data.type}`, timestamp: new Date().toISOString() });
                        }
                    } catch (error) {
                        console.error("[Chat] 解析或處理收到的訊息時出錯:", error, "原始數據:", e.data);
                        // Display a generic error message in chat
                        addChatMessage({ type: 'system', message: '處理收到的訊息時發生錯誤。', timestamp: new Date().toISOString() });
                    }
                };

                // On Connection Close
                chatSocket.onclose = function(e) {
                    console.error('[Chat] WebSocket 連接關閉。 Code:', e.code, 'Reason:', e.reason || '(無)', 'Clean:', e.wasClean);
                    // Disable input/submit
                    if (chatMessageInput) chatMessageInput.disabled = true;
                    if (chatMessageSubmit) chatMessageSubmit.disabled = true;
                    clearReplyState(); // Clear reply state on close

                    const wasConnected = chatSocket === this; // Check if this is the currently active socket closing
                    if (wasConnected) chatSocket = null; // Nullify the socket variable

                    // Define WebSocket close codes that usually don't require automatic reconnection
                    // 1000: Normal Closure, 1001: Going Away (e.g., server shut down, page navigation)
                    // 1005: No Status Received (might happen on browser close)
                    const normalCloseCodes = [1000, 1001, 1005];

                    // Attempt to reconnect only if the closure was unclean or unexpected, and within attempt limits
                    if (!e.wasClean && !normalCloseCodes.includes(e.code) && reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        const delaySeconds = reconnectDelay / 1000;
                        console.log(`[Chat] ${delaySeconds} 秒後重連 (嘗試 ${reconnectAttempts}/${maxReconnectAttempts})`);
                        // Show reconnection message in chat
                        if (chatMessages) addChatMessage({ type: 'system', message: `連接斷開，${delaySeconds}秒後嘗試重新連接...`, timestamp: new Date().toISOString() });
                        setTimeout(connectChatSocket, reconnectDelay); // Schedule reconnection
                    } else if (normalCloseCodes.includes(e.code)) {
                        // Normal closure, just indicate connection closed
                        if (chatMessages) addChatMessage({ type: 'system', message: '連接已關閉。', timestamp: new Date().toISOString() });
                         console.log("[Chat] Connection closed normally or going away. No automatic reconnection.")
                    } else {
                        // Max reconnection attempts reached or other non-retrying close code
                        if (chatMessages) addChatMessage({ type: 'system', message: '無法重新連接。請刷新頁面重試。', timestamp: new Date().toISOString() });
                         console.log("[Chat] Max reconnection attempts reached or non-retrying close code. Giving up.")
                    }
                };

                // On Connection Error
                chatSocket.onerror = function(err) {
                    // This event often precedes the onclose event when there's a connection issue
                    console.error('[Chat] WebSocket 錯誤:', err);
                    // Clear reply state on error as well
                    clearReplyState();
                    // Display a generic error message
                    if (chatMessages) addChatMessage({ type: 'system', message: '發生連接錯誤。', timestamp: new Date().toISOString() });
                    // The onclose event will likely handle the reconnection logic if needed
                };
                // --- End WebSocket Event Listeners ---

            } // End of connectChatSocket function

            /**
             * Handles WebSocket connection errors during setup or potentially later.
             * Updates UI state and logs the error.
             * @param {string} [errorMessage="連接錯誤"] - The error message to display/log.
             */
            function handleConnectionError(errorMessage = "連接錯誤") {
                 console.error(`[Chat] 處理連接錯誤: ${errorMessage}`);
                 clearReplyState();
                 if (chatMessageInput) chatMessageInput.disabled = true;
                 if (chatMessageSubmit) chatMessageSubmit.disabled = true;

                 // Attempt to clean up the possibly problematic socket instance
                 if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED && chatSocket.readyState !== WebSocket.CLOSING) {
                     console.log("[Chat] 嘗試關閉錯誤狀態的 WebSocket...");
                     // Remove listeners to prevent potential issues during forced close
                     chatSocket.onerror = chatSocket.onclose = chatSocket.onopen = chatSocket.onmessage = null;
                     try {
                         chatSocket.close(1011, "Client-side connection error"); // Use an appropriate close code
                     } catch (e) {
                         console.warn("[Chat] Error during forced close in handleConnectionError:", e);
                     }
                 }
                 chatSocket = null; // Ensure socket variable is nullified

                 // Display error message in chat
                 if (chatMessages) {
                     addChatMessage({ type: 'system', message: `連接失敗: ${errorMessage}。`, timestamp: new Date().toISOString() });
                 }
            } // End of handleConnectionError function

            // --- UI Event Listener Setup ---

            // Send Button Click
            if (chatMessageSubmit) {
                chatMessageSubmit.addEventListener('click', sendMessage);
            }

            // Input Field Enter Key Press (without Shift)
            if (chatMessageInput) {
                chatMessageInput.addEventListener('keypress', function(e) {
                    // Send on Enter key unless Shift is also pressed (for new lines)
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault(); // Prevent default Enter behavior (like form submission)
                        // Check connection before sending
                        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                            sendMessage();
                        } else {
                            console.warn("[Chat] Enter pressed but WebSocket not open. Message not sent.");
                             addChatMessage({ type: 'system', message: '錯誤：未連接，無法發送訊息。', timestamp: new Date().toISOString() });
                        }
                    }
                });

                // Input Field Escape Key Press (to cancel reply)
                 chatMessageInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape' && currentReplyTo) { // Check if currently replying
                        e.preventDefault(); // Prevent potential default Esc behavior
                        clearReplyState(); // Cancel the reply
                    }
                 });
            }

            // Cancel Reply Button Click
            if (cancelReplyBtn) {
                cancelReplyBtn.addEventListener('click', clearReplyState);
            }

            // --- Event Delegation for Inline Reply Buttons and Quote Previews ---
            if (chatMessages) {
                chatMessages.addEventListener('click', function(event) {
                    // 1. Check for Inline Reply Button Click
                    const replyButton = event.target.closest('.reply-trigger-btn');
                    if (replyButton) {
                        event.stopPropagation(); // Prevent triggering other listeners

                        // Get data stored on the button
                        const messageId = replyButton.dataset.messageId;
                        const username = replyButton.dataset.username;
                        const snippet = replyButton.dataset.textSnippet;

                        // Ensure all necessary data is present
                        if (messageId && username && snippet !== undefined) {
                            console.log(`[Chat] Reply button clicked for message ID: ${messageId}`);
                            // Set the reply state
                            currentReplyTo = {
                                messageId: messageId,
                                username: username,
                                text: snippet // Use the pre-generated snippet
                            };
                            // Update and show the reply preview bar
                            if (replyQuoteDisplay && replyQuoteContent) {
                                const userStrong = replyQuoteContent.querySelector('.reply-quote-user');
                                const textSpan = replyQuoteContent.querySelector('.reply-quote-text');
                                if(userStrong) userStrong.textContent = username;
                                if(textSpan) textSpan.textContent = snippet;
                                replyQuoteDisplay.style.display = 'flex'; // Show the bar
                            }
                            // Focus the input field for quick typing
                            if (chatMessageInput) chatMessageInput.focus();
                        } else {
                            // Log a warning if data attributes are missing
                            console.warn('[Chat] Reply button missing required data attributes (messageId, username, textSnippet).', replyButton.dataset);
                        }
                        return; // Stop further processing for this click
                    } // End if replyButton

                    // 2. Check for Quote Preview Click
                    const quotePreview = event.target.closest('.quoted-message-preview');
                    if (quotePreview) {
                        event.stopPropagation(); // Prevent triggering parent actions
                        const replyToId = quotePreview.dataset.replyToId; // Get the ID of the original message
                        console.log(`Clicked quote preview for message ID: ${replyToId}`);
                        const originalMessageElement = chatMessages.querySelector(`.chat-message[data-message-id="${replyToId}"]`);
                        if (originalMessageElement) {
                             // Scroll to and highlight the original message
                            originalMessageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            originalMessageElement.style.transition = 'background-color 0.5s ease';
                            originalMessageElement.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                            setTimeout(() => { originalMessageElement.style.backgroundColor = ''; }, 1500);
                        } else {
                            console.warn(`Original message element with ID ${replyToId} not found.`);
                            // Optionally notify user that the message isn't currently loaded
                        }
                        return; // Stop further processing
                    } // End if quotePreview

                    // Add other delegated event handlers here if needed (e.g., clicking user names)

                }); // End chatMessages click listener
            }
            // --- End Event Delegation ---


            // --- MutationObserver for Chat Modal Visibility ---
            // Monitors changes to the chat modal's style attribute to detect when it's shown/hidden
            const chatModalObserver = new MutationObserver((mutationsList) => {
                for(let mutation of mutationsList) {
                    // Check if the 'style' attribute was the one that changed
                    if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                        // Get the current display style of the modal
                        const displayStyle = window.getComputedStyle(chatModal).display;
                        const isChatVisible = displayStyle === 'block'; // Check if modal is visible

                        // --- Actions when Modal becomes VISIBLE ---
                        if (isChatVisible) {
                            // Clear unread indicator if it was set
                            if (hasUnread) {
                                console.log("[Chat] 聊天 Modal 變為可見，清除未讀標記。");
                                hasUnread = false;
                                if (chatUnreadIndicator) { chatUnreadIndicator.style.display = 'none'; }
                            }
                            // Scroll to the bottom when opened
                            scrollToBottom();
                            // Focus the input field shortly after opening
                            setTimeout(() => {
                                if (chatMessageInput && !chatMessageInput.disabled) chatMessageInput.focus();
                            }, 100); // Small delay can help ensure focus works

                            // Check WebSocket connection state when opening
                            if (!chatSocket || chatSocket.readyState === WebSocket.CLOSED || chatSocket.readyState === WebSocket.CLOSING) {
                                 console.log("[Chat] 聊天 Modal 打開，但 WebSocket 未連接或已關閉，嘗試重新連接...");
                                 reconnectAttempts = 0; // Reset attempts when manually opening
                                 connectChatSocket(); // Initiate connection
                            }
                        }
                        // --- Actions when Modal becomes HIDDEN ---
                        else {
                             clearReplyState(); // Cancel any active reply when modal is closed
                             console.log("[Chat] Chat modal hidden. Cleared reply state.");
                        }
                    }
                }
            });

            // Start observing the chat modal if it exists
            if (chatModal) {
                console.log("[Chat] Starting MutationObserver for #chatModal style attribute.");
                chatModalObserver.observe(chatModal, {
                    attributes: true, // Observe attribute changes
                    attributeFilter: ['style'] // Only care about the style attribute
                });
            } else {
                 console.error("[Chat] Cannot start MutationObserver: #chatModal element not found.");
            }
            // --- End MutationObserver ---


            // --- Initial WebSocket Connection ---
            // Attempt the first connection only once after the script loads
            if (!initialConnectionAttempted) {
                 console.log("[Chat] 嘗試初始 WebSocket 連接...");
                 connectChatSocket();
                 initialConnectionAttempted = true; // Set flag to prevent re-attempts by this block
            }
            // --- End Initial Connection ---

            console.log("[Chat] 聊天室腳本核心邏輯初始化完畢 (V9 - Display User Title)。");

        }, 150); // End of setTimeout execution block

    }); // End of DOMContentLoaded event listener
})(); // End of IIFE