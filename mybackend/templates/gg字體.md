font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;



<!-- 標籤樣式 -->
/* 標籤顏色 */
.label.newcomer, .label.hot, .label.exclusive {
  background: rgba(0, 123, 255, 0.1); /* 統一淡藍 */
  color: #007bff;
  border: 1px solid #007bff;
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
}
<!-- 時段效果 -->
.time-slot {
  display: inline-block;
  background-color: #e0f7fa; /* 淺藍綠色背景 */
  color: #007a99; /* 深藍綠色文字 */
  padding: 0.2rem 0.5rem; /* 內邊距 */
  border-radius: 4px; /* 小圓角 */
  margin: 0.15rem 0.2rem; /* 間距 */
  font-size: 0.85rem; /* 字體稍小 */
  white-space: nowrap; /* 防止斷行 */
  border: 1px solid #b3eaf5; /* 同色系邊框 */
  line-height: 1.3;
}
<!-- html to figma -->
https://www.figma.com/community/plugin/1159123024924461424/html.to.design
<!-- end -->
1678
<!-- 面板&遮罩優先級 -->
會員 1000
選單 1000
左側遮罩 1050
左側面板 1150
相關面板 2999
心得面板 3000
底部遮罩 3000
底部選單 3500
<!-- 標籤漸變色 -->
 .label.label--style-hidden {
        background: linear-gradient(45deg, rgba(111, 66, 193, 0.8), rgba(0, 123, 255, 0.8)); /* 紫色到藍色漸變 */
        color: #ffffff; /* 白色文字 */
        border: none; /* 移除邊框可能效果更好 */
        /* font-style: normal; */
        padding: 0.15em 0.5em; /* 可能需要微調 padding */